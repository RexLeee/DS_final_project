import { useState, useEffect } from 'react';

interface TimeLeft {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  total: number;
  isExpired: boolean;
}

export function useCountdown(targetDate: Date | string | undefined): TimeLeft {
  const calculateTimeLeft = (): TimeLeft => {
    if (!targetDate) {
      return { days: 0, hours: 0, minutes: 0, seconds: 0, total: 0, isExpired: true };
    }

    // Ensure the date string is parsed as UTC if it doesn't have timezone info
    let target: Date;
    if (typeof targetDate === 'string') {
      // If the string doesn't end with 'Z' or timezone offset, treat it as UTC
      const hasTimezone = targetDate.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(targetDate);
      target = new Date(hasTimezone ? targetDate : targetDate + 'Z');
    } else {
      target = targetDate;
    }
    const difference = target.getTime() - Date.now();

    if (difference <= 0) {
      return { days: 0, hours: 0, minutes: 0, seconds: 0, total: 0, isExpired: true };
    }

    return {
      days: Math.floor(difference / (1000 * 60 * 60 * 24)),
      hours: Math.floor((difference / (1000 * 60 * 60)) % 24),
      minutes: Math.floor((difference / 1000 / 60) % 60),
      seconds: Math.floor((difference / 1000) % 60),
      total: difference,
      isExpired: false,
    };
  };

  const [timeLeft, setTimeLeft] = useState<TimeLeft>(calculateTimeLeft);

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft(calculateTimeLeft());
    }, 1000);

    return () => clearInterval(timer);
  }, [targetDate]);

  return timeLeft;
}

export function formatTimeLeft(timeLeft: TimeLeft): string {
  if (timeLeft.isExpired) {
    return '已結束';
  }

  const parts: string[] = [];

  if (timeLeft.days > 0) {
    parts.push(`${timeLeft.days}天`);
  }
  if (timeLeft.hours > 0 || parts.length > 0) {
    parts.push(`${timeLeft.hours.toString().padStart(2, '0')}時`);
  }
  parts.push(`${timeLeft.minutes.toString().padStart(2, '0')}分`);
  parts.push(`${timeLeft.seconds.toString().padStart(2, '0')}秒`);

  return parts.join(' ');
}
