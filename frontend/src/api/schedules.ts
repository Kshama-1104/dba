import { apiClient } from "./client";
import { BlogSchedule, BlogScheduleDetail } from "../types";

export interface CreateSchedulePayload {
  local_scheduled_time: string; // e.g. 2026-10-15T09:30:00
  timezone: string; // canonical IANA e.g. "Asia/Kolkata", "America/New_York"
  target_revision_id?: number;
}

export interface ReschedulePayload {
  local_scheduled_time: string;
  timezone?: string;
}

export const schedulesApi = {
  createSchedule: (blogId: number, payload: CreateSchedulePayload) =>
    apiClient.post<BlogSchedule>(`/api/v1/blogs/${blogId}/schedules`, payload),

  listBlogSchedules: (blogId: number) =>
    apiClient.get<BlogSchedule[]>(`/api/v1/blogs/${blogId}/schedules`),

  getSchedule: (scheduleId: number) =>
    apiClient.get<BlogScheduleDetail>(`/api/v1/schedules/${scheduleId}`),

  reschedule: (scheduleId: number, payload: ReschedulePayload) =>
    apiClient.post<BlogSchedule>(
      `/api/v1/schedules/${scheduleId}/reschedule`,
      payload
    ),

  cancelSchedule: (scheduleId: number, reason?: string) =>
    apiClient.post<BlogSchedule>(`/api/v1/schedules/${scheduleId}/cancel`, {
      reason,
    }),
};
