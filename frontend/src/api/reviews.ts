import { apiClient } from "./client";
import {
  BlogReview,
  BlogReviewDetail,
  PendingReviewItem,
  ReviewDecision,
} from "../types";

export interface ReviewDecisionPayload {
  decision: ReviewDecision;
  feedback?: string;
  reviewer_comment?: string;
}

export const reviewsApi = {
  listPendingReviews: (skip = 0, limit = 50) =>
    apiClient.get<PendingReviewItem[]>(
      `/api/v1/blogs/reviews/pending?skip=${skip}&limit=${limit}`
    ),

  submitForReview: (blogId: number, submissionNote?: string) =>
    apiClient.post<BlogReview>(`/api/v1/blogs/${blogId}/submit-for-review`, {
      submission_note: submissionNote,
    }),

  withdrawReview: (blogId: number) =>
    apiClient.post<BlogReview>(`/api/v1/blogs/${blogId}/withdraw-review`),

  getReviewHistory: (blogId: number, skip = 0, limit = 50) =>
    apiClient.get<BlogReview[]>(
      `/api/v1/blogs/${blogId}/reviews?skip=${skip}&limit=${limit}`
    ),

  getReviewDetail: (blogId: number, reviewId: number) =>
    apiClient.get<BlogReviewDetail>(
      `/api/v1/blogs/${blogId}/reviews/${reviewId}`
    ),

  decideReview: (
    blogId: number,
    reviewId: number,
    payload: ReviewDecisionPayload
  ) =>
    apiClient.post<BlogReview>(
      `/api/v1/blogs/${blogId}/reviews/${reviewId}/decide`,
      payload
    ),
};
