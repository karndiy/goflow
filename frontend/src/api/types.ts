export interface User {
  id: string
  email: string
  is_active: boolean
  created_at: string
}

export interface Workspace {
  id: string
  name: string
  timezone: string
  created_at: string
  updated_at: string
}

export type ContentStatus =
  | 'draft'
  | 'scheduled'
  | 'publishing'
  | 'published'
  | 'partial_failure'
  | 'failed'

export interface Content {
  id: string
  workspace_id: string
  title: string
  status: ContentStatus
  created_at: string
  updated_at: string
}

export interface ContentListResponse {
  items: Content[]
  total: number
  limit: number
  offset: number
}

export type MediaType = 'none' | 'image' | 'video' | 'carousel'

export interface ContentVariant {
  id: string
  content_id: string
  platform: string
  text: string
  media_type: MediaType
  payload_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface SocialAccount {
  id: string
  workspace_id: string
  platform: string
  external_account_id: string
  account_name: string
  status: string
  created_at: string
}

export type JobStatus =
  | 'scheduled'
  | 'queued'
  | 'publishing'
  | 'processing'
  | 'published'
  | 'failed'
  | 'cancelled'
  | 'unknown'

export interface PublishAttempt {
  id: string
  attempt_number: number
  status: string
  provider_request_id: string | null
  error_code: string | null
  error_message: string | null
  created_at: string
}

export interface PublishingJob {
  id: string
  content_variant_id: string
  social_account_id: string
  scheduled_at: string
  status: JobStatus
  external_post_id: string | null
  attempts: number
  last_error: string | null
  created_at: string
  updated_at: string
}

export interface PublishingJobDetail extends PublishingJob {
  publish_attempts: PublishAttempt[]
}

export interface JobListResponse {
  items: PublishingJob[]
  total: number
  limit: number
  offset: number
}

export interface CalendarEntry {
  job_id: string
  content_id: string
  content_title: string
  platform: string
  social_account_id: string
  account_name: string
  scheduled_at: string
  status: JobStatus
}

export interface DashboardSummary {
  content_by_status: Record<string, number>
  jobs_by_status: Record<string, number>
  accounts: { platform: string; status: string; count: number }[]
}

export interface PlatformCredential {
  platform: string
  app_id: string
  has_secret: boolean
  updated_at: string
}

export interface AuditLogEntry {
  id: string
  actor_email: string
  action: string
  target_type: string | null
  target_id: string | null
  details: Record<string, unknown>
  created_at: string
}

export interface AuditLogListResponse {
  items: AuditLogEntry[]
  total: number
  limit: number
  offset: number
}
