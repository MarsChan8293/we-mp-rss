export interface MessageTask {
  id: string
  name: string
  message_type: number
  message_template: string
  web_hook_url: string
  headers?: string
  cookies?: string
  email_to?: string
  email_cc?: string
  email_subject_template?: string
  email_content_type?: string
  mps_id: any // JSON类型
  status: number
  cron_exp?: string
  created_at?: string
  updated_at?: string
}

export interface MessageTaskCreate {
  name: string
  message_type: number
  message_template: string
  web_hook_url: string
  headers?: string
  cookies?: string
  email_to?: string
  email_cc?: string
  email_subject_template?: string
  email_content_type?: string
  mps_id: any
  status?: number
  cron_exp?: string
}

export interface MessageTaskUpdate {
  name?: string
  message_type?: number
  message_template?: string
  web_hook_url?: string
  headers?: string
  cookies?: string
  email_to?: string
  email_cc?: string
  email_subject_template?: string
  email_content_type?: string
  mps_id?: any
  status?: number
  cron_exp?: string
}

export interface MessageTaskTestRequest {
  name?: string
  message_type?: number
  message_template?: string
  web_hook_url?: string
  headers?: string
  cookies?: string
  email_to?: string
  email_cc?: string
  email_subject_template?: string
  email_content_type?: string
  mps_id?: string
}

export interface MessageTaskDebugRequest {
  url: string
  message_type: number
  headers: Record<string, string>
  cookies?: Record<string, string> | null
  payload: string
}

export interface MessageTaskDebugResponse {
  status_code: number | null
  body: unknown
  raw_text: string | null
}

export interface MessageTaskTestResult {
  success: boolean
  summary: string
  request: MessageTaskDebugRequest
  response: MessageTaskDebugResponse
  error: string | null
}

export interface MessageTaskTestData {
  task_id: string
  task_name: string
  message_type: number
  feed_name: string
  result: MessageTaskTestResult
}
