// Goals API Service
// Communicates with backend for goals persistence

import { api } from './api';
import { TradingGoals, CommitmentLogEntry, StreakData } from '@/types/patterns';

export interface GoalsApiResponse {
  goals: TradingGoals & { id: string; broker_account_id: string };
  commitment_log: CommitmentLogEntry[];
  streak: StreakData;
  is_review_open: boolean;
  days_until_review: number;
}

export async function fetchGoals(brokerAccountId: string): Promise<GoalsApiResponse | null> {
  try {
    const response = await api.get('/api/goals/', {
      params: { broker_account_id: brokerAccountId }
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching goals:', error);
    return null;
  }
}

export async function updateGoals(
  brokerAccountId: string,
  updates: Partial<TradingGoals>,
  reason?: string
): Promise<TradingGoals | null> {
  try {
    const response = await api.put('/api/goals/', {
      ...updates,
      reason,
    }, {
      params: { broker_account_id: brokerAccountId }
    });
    return response.data;
  } catch (error) {
    console.error('Error updating goals:', error);
    return null;
  }
}

export async function logGoalBroken(
  brokerAccountId: string,
  goalName: string,
  cost: number = 0
): Promise<boolean> {
  try {
    await api.post('/api/goals/log-broken', null, {
      params: { broker_account_id: brokerAccountId, goal_name: goalName, cost }
    });
    return true;
  } catch (error) {
    console.error('Error logging goal broken:', error);
    return false;
  }
}

export async function updateStreak(
  brokerAccountId: string,
  allGoalsFollowed: boolean,
  goalsBroken: string[] = []
): Promise<{ streak: number; longest: number } | null> {
  try {
    const response = await api.post('/api/goals/streak/increment', {
      all_goals_followed: allGoalsFollowed,
      goals_broken: goalsBroken,
    }, {
      params: { broker_account_id: brokerAccountId }
    });
    return response.data;
  } catch (error) {
    console.error('Error updating streak:', error);
    return null;
  }
}

export async function fetchStreak(brokerAccountId: string): Promise<StreakData | null> {
  try {
    const response = await api.get('/api/goals/streak', {
      params: { broker_account_id: brokerAccountId }
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching streak:', error);
    return null;
  }
}
