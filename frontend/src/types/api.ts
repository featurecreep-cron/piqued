// Auto-generated from piqued.api.v1.schemas — do not edit manually.
// Regenerate with: PYTHONPATH=. python scripts/generate_types.py --write

export interface SectionItem {
  id: number
  article_id: number
  article_title: string
  feed_title: string
  heading: string | null
  summary: string
  topic_tags: string[]
  score: number
  reasoning: string | null
  is_surprise: boolean
  has_humor: boolean
  has_surprise_data: boolean
  has_actionable_advice: boolean
  article_url: string | null
  published_at: string | null
}

export interface SectionList {
  sections: SectionItem[]
  date: string
  dates_available: string[]
  threshold: number
  surprise_section_ids: number[]
}

export interface FeedItem {
  id: number
  title: string
  url: string | null
  category: string
  active: boolean
  content_quality: string
  article_count: number
  unread_count?: number | null
}

export interface FeedList {
  feeds: FeedItem[]
  categories: Record<string, number[]>
}

export interface ArticleSummary {
  id: number
  title: string
  url: string | null
  published_at: string | null
  status: string
  section_count: number
}

export interface FeedDetail {
  feed: FeedItem
  articles: ArticleSummary[]
}

export interface ArticleSection {
  id: number
  heading: string | null
  summary: string
  topic_tags: string[]
  score: number
  reasoning: string | null
  is_surprise: boolean
  has_humor: boolean
  has_surprise_data: boolean
  has_actionable_advice: boolean
}

export interface ArticleDetail {
  id: number
  title: string
  url: string | null
  feed_title: string
  published_at: string | null
  status: string
  sections: ArticleSection[]
}

export interface WeightItem {
  topic: string
  weight: number
  feedback_count: number
  updated_at: string | null
}

export interface UserProfileResponse {
  profile_text: string
  profile_version: number
  pending_feedback_count: number
  last_synthesized_at: string | null
  weights: WeightItem[]
}

export interface ProfileEditRequest {
  profile_text: string
}

export interface UserInfo {
  id: number
  username: string
  email: string | null
  role: string
}

export interface UserList {
  users: UserInfo[]
}

export interface SettingsResponse {
  settings: Record<string, string>
  is_admin: boolean
}

export interface ConnectionTestResult {
  ok: boolean
  detail: string
}

export interface ProcessingLogEntry {
  id: number
  article_id: number | null
  article_title: string | null
  stage: string
  status: string
  detail: string | null
  tokens_used: number | null
  duration_ms: number | null
  created_at: string
}

export interface ProcessingLogList {
  entries: ProcessingLogEntry[]
  limit: number
  offset: number
  total: number
}

export interface FeedbackRequest {
  section_id: number
  rating: number
  reason?: string | null
}

export interface FeedbackResult {
  ok: boolean
  direction: string
}

export interface SyncResult {
  ok: boolean
  total: number
  added: number
}

export interface ClickThroughRequest {
  section_id: number
}

export interface DownweightRequest {
  tag: string
}

export interface CreateUserRequest {
  username: string
  password: string
  role?: string
}

export interface ChangeRoleRequest {
  role: string
}

export interface ApiKeyCreate {
  name?: string
}

export interface ApiKeyCreated {
  id: number
  name: string
  key: string
}

export interface ApiKeyItem {
  id: number
  name: string
  last_used_at: string | null
  created_at: string
}

export interface ApiKeyList {
  keys: ApiKeyItem[]
}

export interface UserPreferences {
  theme?: string
  layout_mode?: string
  items_per_page?: number
  column_config?: string[] | null
}

export interface UserPreferencesUpdate {
  theme?: string | null
  layout_mode?: string | null
  items_per_page?: number | null
  column_config?: string[] | null
}

export interface BootstrapIngestRequest {
  feed_ids: number[]
}

export interface BootstrapIngestResult {
  ok: boolean
  section_count: number
}

export interface BootstrapCompleteResult {
  ok: boolean
  sections_scored: number
}

export interface BootstrapStatusResponse {
  bootstrap_complete: boolean
  has_sections: boolean
}
