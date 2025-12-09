#!/bin/bash
# ============================================
# GCP Deployment Script for Flash Sale System
# ============================================

set -e

# ============================================
# Configuration
# ============================================
export PROJECT_ID="ds-final-project-480207"
export REGION="us-central1"
export ZONE="us-central1-a"
export CLUSTER_NAME="flash-sale-cluster"
export VPC_NAME="flash-sale-vpc"
export SQL_INSTANCE="flash-sale-db"
export REDIS_INSTANCE="flash-sale-redis"
export REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/flash-sale-repo"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================
# Step 1: Configure GCP Project
# ============================================
setup_project() {
    echo_info "Setting up GCP project..."

    gcloud config set project $PROJECT_ID
    gcloud config set compute/region $REGION
    gcloud config set compute/zone $ZONE

    echo_info "Enabling required APIs..."
    gcloud services enable \
        container.googleapis.com \
        sqladmin.googleapis.com \
        redis.googleapis.com \
        artifactregistry.googleapis.com \
        compute.googleapis.com \
        servicenetworking.googleapis.com
}

# ============================================
# Step 2: Create Artifact Registry
# ============================================
create_registry() {
    echo_info "Creating Artifact Registry..."

    if gcloud artifacts repositories describe flash-sale-repo --location=$REGION &>/dev/null; then
        echo_warn "Artifact Registry already exists, skipping..."
    else
        gcloud artifacts repositories create flash-sale-repo \
            --repository-format=docker \
            --location=$REGION \
            --description="Flash Sale System Docker Images"
    fi

    echo_info "Configuring Docker authentication..."
    gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet
}

# ============================================
# Step 3: Create VPC Network
# ============================================
create_vpc() {
    echo_info "Creating VPC network..."

    if gcloud compute networks describe $VPC_NAME &>/dev/null; then
        echo_warn "VPC network already exists, skipping..."
    else
        gcloud compute networks create $VPC_NAME \
            --subnet-mode=auto \
            --bgp-routing-mode=regional
    fi

    echo_info "Creating private service access..."
    if gcloud compute addresses describe google-managed-services-flash-sale --global &>/dev/null; then
        echo_warn "Private service access already exists, skipping..."
    else
        gcloud compute addresses create google-managed-services-flash-sale \
            --global \
            --purpose=VPC_PEERING \
            --prefix-length=16 \
            --network=$VPC_NAME

        gcloud services vpc-peerings connect \
            --service=servicenetworking.googleapis.com \
            --ranges=google-managed-services-flash-sale \
            --network=$VPC_NAME

        echo_info "Waiting for VPC peering to be fully established..."
        sleep 60
    fi
}

# ============================================
# Step 4: Create Cloud SQL
# ============================================
create_cloud_sql() {
    echo_info "Creating Cloud SQL instance (this may take several minutes)..."

    if gcloud sql instances describe $SQL_INSTANCE &>/dev/null; then
        echo_warn "Cloud SQL instance already exists, skipping..."
    else
        # Retry mechanism for Cloud SQL creation
        # VPC peering may still be propagating, so we retry on failure
        MAX_RETRIES=3
        RETRY_COUNT=0
        SUCCESS=false

        while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
            RETRY_COUNT=$((RETRY_COUNT + 1))
            echo_info "Attempt $RETRY_COUNT of $MAX_RETRIES to create Cloud SQL..."

            # Optimized for 1000 VU load testing
            # 2 vCPU, 4GB RAM to handle high concurrent connections
            if gcloud sql instances create $SQL_INSTANCE \
                --database-version=POSTGRES_15 \
                --tier=db-custom-2-4096 \
                --region=$REGION \
                --network=$VPC_NAME \
                --no-assign-ip \
                --storage-size=10GB \
                --storage-type=SSD \
                --no-storage-auto-increase \
                --availability-type=ZONAL; then
                echo_info "Cloud SQL instance created successfully!"
                SUCCESS=true
                break
            else
                if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                    echo_warn "Cloud SQL creation failed. Waiting 60 seconds before retry..."
                    sleep 60
                fi
            fi
        done

        if [ "$SUCCESS" = false ]; then
            echo_error "Cloud SQL creation failed after $MAX_RETRIES attempts."
            echo_error "Please check VPC peering status and try again."
            return 1
        fi

        echo_info "Setting database password..."
        echo_warn "Please set a secure password for the postgres user:"
        read -s -p "Enter password: " DB_PASSWORD
        echo

        gcloud sql users set-password postgres \
            --instance=$SQL_INSTANCE \
            --password="$DB_PASSWORD"

        echo_info "Creating database..."
        gcloud sql databases create flash_sale \
            --instance=$SQL_INSTANCE

        # Set max_connections=200 for high concurrency (PgBouncer 6 pods × 30 = 180 connections)
        # Default ~100 is insufficient for 1000 VU load testing
        echo_info "Setting max_connections=200 for high concurrency support..."
        gcloud sql instances patch $SQL_INSTANCE \
            --database-flags=max_connections=200
        echo_info "Waiting for Cloud SQL to restart with new configuration..."
        sleep 60
    fi

    CLOUD_SQL_IP=$(gcloud sql instances describe $SQL_INSTANCE --format='value(ipAddresses[0].ipAddress)')
    echo_info "Cloud SQL Private IP: $CLOUD_SQL_IP"
}

# ============================================
# Step 5: Create Memorystore (Redis)
# ============================================
create_memorystore() {
    echo_info "Creating Memorystore Redis instance (this may take several minutes)..."

    if gcloud redis instances describe $REDIS_INSTANCE --region=$REGION &>/dev/null; then
        echo_warn "Memorystore instance already exists, skipping..."
    else
        # Demo-optimized: Using 1GB Basic tier for cost efficiency
        # For production, consider 5GB+ Standard tier for HA
        gcloud redis instances create $REDIS_INSTANCE \
            --size=1 \
            --region=$REGION \
            --tier=basic \
            --redis-version=redis_7_0 \
            --network=$VPC_NAME \
            --connect-mode=PRIVATE_SERVICE_ACCESS
    fi

    REDIS_IP=$(gcloud redis instances describe $REDIS_INSTANCE --region=$REGION --format='value(host)')
    echo_info "Memorystore Redis IP: $REDIS_IP"
}

# ============================================
# Step 6: Create GKE Cluster
# ============================================
create_gke_cluster() {
    echo_info "Creating GKE Autopilot cluster (this may take several minutes)..."

    if gcloud container clusters describe $CLUSTER_NAME --region=$REGION &>/dev/null; then
        echo_warn "GKE cluster already exists, skipping..."
    else
        gcloud container clusters create-auto $CLUSTER_NAME \
            --region=$REGION \
            --network=$VPC_NAME \
            --subnetwork=$VPC_NAME \
            --enable-private-nodes
    fi

    echo_info "Getting cluster credentials..."
    gcloud container clusters get-credentials $CLUSTER_NAME --region=$REGION
}

# ============================================
# Step 7: Reserve Static IP
# ============================================
create_static_ip() {
    echo_info "Reserving static IP for load balancer..."

    if gcloud compute addresses describe flash-sale-ip --global &>/dev/null; then
        echo_warn "Static IP already exists, skipping..."
    else
        gcloud compute addresses create flash-sale-ip --global --ip-version=IPV4
    fi

    INGRESS_IP=$(gcloud compute addresses describe flash-sale-ip --global --format='value(address)')
    echo_info "Static IP for Ingress: $INGRESS_IP"
}

# ============================================
# Step 8: Build and Push Docker Images
# ============================================
build_and_push_images() {
    echo_info "Building and pushing Docker images..."

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

    # Use buildx with linux/amd64 platform for GKE compatibility
    # This ensures images work on GKE even when built on Apple Silicon Macs
    echo_info "Building backend image (linux/amd64)..."
    docker buildx build --platform linux/amd64 \
        -t ${REGISTRY}/backend:latest \
        --push \
        ${PROJECT_ROOT}/backend

    echo_info "Building frontend image (linux/amd64)..."
    docker buildx build --platform linux/amd64 \
        -t ${REGISTRY}/frontend:latest \
        --push \
        ${PROJECT_ROOT}/frontend

    # Pull and push PgBouncer image (edoburu/pgbouncer) for GKE
    # This avoids Docker Hub rate limits and ensures correct architecture
    echo_info "Pulling and pushing PgBouncer image (linux/amd64)..."
    docker pull --platform linux/amd64 edoburu/pgbouncer:latest
    docker tag edoburu/pgbouncer:latest ${REGISTRY}/pgbouncer:latest
    docker push ${REGISTRY}/pgbouncer:latest

    echo_info "Verifying images..."
    gcloud artifacts docker images list ${REGISTRY}
}

# ============================================
# Step 9: Deploy to GKE
# ============================================
deploy_to_gke() {
    echo_info "Deploying to GKE..."

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    K8S_DIR="${PROJECT_ROOT}/k8s"

    # Get infrastructure IPs
    echo_info "Getting Cloud SQL IP..."
    CLOUD_SQL_IP=$(gcloud sql instances describe $SQL_INSTANCE --format='value(ipAddresses[0].ipAddress)')
    echo_info "Cloud SQL IP: $CLOUD_SQL_IP"

    echo_info "Getting Redis IP..."
    REDIS_IP=$(gcloud redis instances describe $REDIS_INSTANCE --region=$REGION --format='value(host)')
    echo_info "Redis IP: $REDIS_IP"

    # Prompt for database password
    echo_warn "Enter the database password you set during Cloud SQL creation:"
    read -s DB_PASSWORD
    echo

    # Generate JWT secret
    JWT_SECRET=$(openssl rand -hex 32)
    echo_info "Generated JWT secret"

    # Generate secrets.yaml with actual values
    # Backend connects to PgBouncer (pgbouncer:5432), NOT directly to Cloud SQL
    echo_info "Generating secrets.yaml (backend -> PgBouncer -> Cloud SQL)..."
    cat > ${K8S_DIR}/secrets.yaml << EOF
apiVersion: v1
kind: Secret
metadata:
  name: flash-sale-secrets
  namespace: flash-sale
type: Opaque
stringData:
  # DATABASE_URL points to PgBouncer service for connection pooling
  # PgBouncer multiplexes connections to Cloud SQL, enabling higher concurrency
  # Direct Cloud SQL: postgresql+asyncpg://postgres:${DB_PASSWORD}@${CLOUD_SQL_IP}:5432/flash_sale
  DATABASE_URL: "postgresql+asyncpg://postgres:${DB_PASSWORD}@pgbouncer:5432/flash_sale"
  JWT_SECRET_KEY: "${JWT_SECRET}"
  REDIS_URL: "redis://${REDIS_IP}:6379/0"
EOF

    # Update pgbouncer-deployment.yaml with actual Cloud SQL IP (preserve yaml file settings)
    echo_info "Updating pgbouncer-deployment.yaml with Cloud SQL IP..."
    sed -i.bak "s|value: \"10\.71\.0\.[0-9]*\"|value: \"${CLOUD_SQL_IP}\"|g" ${K8S_DIR}/pgbouncer-deployment.yaml
    rm -f ${K8S_DIR}/pgbouncer-deployment.yaml.bak

    # Update pgbouncer-secrets with database password
    echo_info "Updating pgbouncer-secrets..."
    sed -i.bak "s|postgresql-password: \".*\"|postgresql-password: \"${DB_PASSWORD}\"|g" ${K8S_DIR}/pgbouncer-deployment.yaml
    rm -f ${K8S_DIR}/pgbouncer-deployment.yaml.bak

    echo_info "Applying Kubernetes manifests..."
    kubectl apply -f ${K8S_DIR}/namespace.yaml
    kubectl apply -f ${K8S_DIR}/configmap.yaml
    kubectl apply -f ${K8S_DIR}/secrets.yaml
    kubectl apply -f ${K8S_DIR}/pgbouncer-deployment.yaml
    kubectl apply -f ${K8S_DIR}/backend-deployment.yaml
    kubectl apply -f ${K8S_DIR}/frontend-deployment.yaml
    kubectl apply -f ${K8S_DIR}/services.yaml
    kubectl apply -f ${K8S_DIR}/ingress.yaml
    kubectl apply -f ${K8S_DIR}/hpa.yaml

    echo_info "Waiting for deployments to be ready..."
    kubectl rollout status deployment/pgbouncer -n flash-sale --timeout=300s
    kubectl rollout status deployment/backend -n flash-sale --timeout=300s
    kubectl rollout status deployment/frontend -n flash-sale --timeout=300s
}

# ============================================
# Step 10: Run Database Migration
# ============================================
run_migration() {
    echo_info "Running database migration..."

    # Get Cloud SQL IP
    CLOUD_SQL_IP=$(gcloud sql instances describe $SQL_INSTANCE --format='value(ipAddresses[0].ipAddress)')
    echo_info "Cloud SQL IP: $CLOUD_SQL_IP"

    # Prompt for database password
    echo_warn "Enter the database password you set during Cloud SQL creation:"
    read -s DB_PASSWORD
    echo

    DATABASE_URL="postgresql+asyncpg://postgres:${DB_PASSWORD}@${CLOUD_SQL_IP}:5432/flash_sale"

    kubectl run migrate --rm -it \
        --image=${REGISTRY}/backend:latest \
        --namespace=flash-sale \
        --restart=Never \
        --env="DATABASE_URL=${DATABASE_URL}" \
        -- alembic upgrade head
}

# ============================================
# Step 11: Verify Deployment
# ============================================
verify_deployment() {
    echo_info "Verifying deployment..."

    echo_info "Pods status:"
    kubectl get pods -n flash-sale

    echo_info "Services status:"
    kubectl get services -n flash-sale

    echo_info "Ingress status:"
    kubectl get ingress -n flash-sale

    echo_info "HPA status:"
    kubectl get hpa -n flash-sale

    INGRESS_IP=$(gcloud compute addresses describe flash-sale-ip --global --format='value(address)')
    echo_info "Application URL: http://${INGRESS_IP}"
}

# ============================================
# Cleanup: Delete All Resources
# ============================================
cleanup_all() {
    echo_warn "This will DELETE all GCP resources for Flash Sale System!"
    echo_warn "Resources to be deleted:"
    echo "  - GKE Cluster: $CLUSTER_NAME"
    echo "  - Cloud SQL: $SQL_INSTANCE"
    echo "  - Memorystore Redis: $REDIS_INSTANCE"
    echo "  - Artifact Registry: flash-sale-repo"
    echo "  - Static IP: flash-sale-ip"
    echo "  - VPC: $VPC_NAME"
    echo ""
    read -p "Are you sure? Type 'yes' to confirm: " confirm

    if [[ "$confirm" != "yes" ]]; then
        echo_info "Cleanup cancelled."
        return
    fi

    echo_info "Deleting GKE cluster..."
    gcloud container clusters delete $CLUSTER_NAME --region=$REGION --quiet 2>/dev/null || echo_warn "GKE cluster not found or already deleted"

    echo_info "Deleting Cloud SQL instance..."
    gcloud sql instances delete $SQL_INSTANCE --quiet 2>/dev/null || echo_warn "Cloud SQL not found or already deleted"

    echo_info "Deleting Memorystore Redis..."
    gcloud redis instances delete $REDIS_INSTANCE --region=$REGION --quiet 2>/dev/null || echo_warn "Redis not found or already deleted"

    echo_info "Deleting Artifact Registry..."
    gcloud artifacts repositories delete flash-sale-repo --location=$REGION --quiet 2>/dev/null || echo_warn "Artifact Registry not found or already deleted"

    echo_info "Deleting Static IP..."
    gcloud compute addresses delete flash-sale-ip --global --quiet 2>/dev/null || echo_warn "Static IP not found or already deleted"

    echo_info "Deleting VPC peering..."
    gcloud compute addresses delete google-managed-services-flash-sale --global --quiet 2>/dev/null || echo_warn "VPC peering address not found"

    echo_info "Deleting VPC network..."
    gcloud compute networks delete $VPC_NAME --quiet 2>/dev/null || echo_warn "VPC not found or already deleted"

    echo_info "Cleanup complete!"
}

# ============================================
# Main Menu
# ============================================
show_menu() {
    echo ""
    echo "============================================"
    echo "   Flash Sale System - GCP Deployment"
    echo "============================================"
    echo ""
    echo "1.  Setup project and enable APIs"
    echo "2.  Create Artifact Registry"
    echo "3.  Create VPC network"
    echo "4.  Create Cloud SQL (PostgreSQL)"
    echo "5.  Create Memorystore (Redis)"
    echo "6.  Create GKE Autopilot cluster"
    echo "7.  Reserve static IP"
    echo "8.  Build and push Docker images"
    echo "9.  Deploy to GKE"
    echo "10. Run database migration"
    echo "11. Verify deployment"
    echo ""
    echo "A.  Run ALL steps (1-11)"
    echo "D.  DELETE all resources (cleanup)"
    echo "Q.  Quit"
    echo ""
}

# ============================================
# Run All Steps
# ============================================
run_all() {
    setup_project
    create_registry
    create_vpc
    create_cloud_sql
    create_memorystore
    create_gke_cluster
    create_static_ip
    build_and_push_images
    deploy_to_gke
    run_migration
    verify_deployment
}

# ============================================
# Main
# ============================================
main() {
    while true; do
        show_menu
        read -p "Select an option: " choice

        case $choice in
            1) setup_project ;;
            2) create_registry ;;
            3) create_vpc ;;
            4) create_cloud_sql ;;
            5) create_memorystore ;;
            6) create_gke_cluster ;;
            7) create_static_ip ;;
            8) build_and_push_images ;;
            9) deploy_to_gke ;;
            10) run_migration ;;
            11) verify_deployment ;;
            [Aa]) run_all ;;
            [Dd]) cleanup_all ;;
            [Qq]) echo "Exiting..."; exit 0 ;;
            *) echo_error "Invalid option" ;;
        esac

        echo ""
        read -p "Press Enter to continue..."
    done
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main
fi
