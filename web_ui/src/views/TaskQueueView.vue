<template>
  <div class="task-queue-view">
    <!-- 顶部状态栏 -->
    <div class="header-bar">
      <div class="header-left">
        <span class="title">任务队列</span>
        <a-tag :color="queueStatus.is_running ? 'green' : 'red'" size="small">
          {{ queueStatus.is_running ? '运行中' : '已停止' }}
        </a-tag>
        <a-tag :color="wsConnected ? 'green' : 'orange'" size="small">
          {{ wsConnected ? '实时' : '轮询' }}
        </a-tag>
      </div>
      <div class="header-right">
        <a-button type="primary" size="small" @click="refreshAll" :loading="loading">
          <template #icon><icon-refresh /></template>
          刷新
        </a-button>
        <a-popconfirm content="确定要清空队列吗？" @ok="handleClearQueue">
          <a-button size="small" status="warning" :loading="clearingQueue">
            <template #icon><icon-delete /></template>
            清空队列
          </a-button>
        </a-popconfirm>
        <a-popconfirm content="确定要清空历史记录吗？" @ok="handleClearHistory">
          <a-button size="small" status="danger" :loading="clearingHistory">
            <template #icon><icon-close /></template>
            清空历史
          </a-button>
        </a-popconfirm>
      </div>
    </div>

    <a-spin :loading="loading" style="width: 100%">
      <!-- 第一行：队列状态 + 当前任务 -->
      <div class="row-layout">
        <!-- 队列状态概览 -->
        <div class="panel status-panel">
          <div class="panel-title">队列状态</div>
          <div class="status-grid">
            <div class="status-item">
              <span class="label">待执行</span>
              <span class="value pending">{{ queueStatus.pending_count ?? 0 }}</span>
            </div>
            <div class="status-item">
              <span class="label">历史数</span>
              <span class="value">{{ queueStatus.history_count ?? 0 }}</span>
            </div>
            <div class="status-item">
              <span class="label">定时任务</span>
              <span class="value">{{ schedulerStatus.job_count }}</span>
            </div>
          </div>
        </div>

        <!-- 当前执行任务 -->
        <div class="panel current-task-panel">
          <div class="panel-title">当前任务</div>
          <div v-if="queueStatus.current_task" class="current-task">
            <div class="task-name">
              <icon-play-arrow-fill style="color: #165dff" />
              {{ queueStatus.current_task.task_name }}
            </div>
            <div class="task-info">
              <span>开始: {{ queueStatus.current_task.start_time }}</span>
              <a-tag color="blue" size="small">{{ queueStatus.current_task.status }}</a-tag>
            </div>
          </div>
          <div v-else class="no-task">
            <icon-pause-circle style="font-size: 24px; color: #c9cdd4" />
            <span>暂无执行中的任务</span>
          </div>
        </div>
      </div>

      <!-- 第二行：待执行任务 + 定时调度器 -->
      <div class="row-layout">
        <!-- 待执行任务列表 -->
        <div class="panel">
          <div class="panel-title">
            待执行任务
            <a-tag v-if="queueStatus.pending_tasks?.length" size="small" color="orangered">
              {{ queueStatus.pending_tasks.length }}
            </a-tag>
          </div>
          <div class="task-list" v-if="queueStatus.pending_tasks && queueStatus.pending_tasks.length > 0">
            <div v-for="(task, index) in queueStatus.pending_tasks.slice(0, 5)" :key="index" class="task-item">
              <a-tag color="arcoblue" size="small">{{ task.task_name }}</a-tag>
            </div>
            <div v-if="queueStatus.pending_tasks.length > 5" class="more-tasks">
              +{{ queueStatus.pending_tasks.length - 5 }} 更多...
            </div>
          </div>
          <div v-else class="no-task">
            <span>暂无待执行任务</span>
          </div>
        </div>

        <!-- 定时调度器 -->
        <div class="panel">
          <div class="panel-title">
            定时调度器
            <a-tag :color="schedulerStatus.running ? 'green' : 'red'" size="small">
              {{ schedulerStatus.running ? '运行中' : '已停止' }}
            </a-tag>
          </div>
          <div class="scheduler-list" v-if="schedulerJobs.length > 0">
            <div v-for="job in schedulerJobs.slice(0, 4)" :key="job.id" class="scheduler-item">
              <span class="job-id">{{ job.id }}</span>
              <span class="job-time">{{ job.next_run_time || '-' }}</span>
            </div>
            <div v-if="schedulerJobs.length > 4" class="more-tasks">
              +{{ schedulerJobs.length - 4 }} 更多...
            </div>
          </div>
          <div v-else class="no-task">
            <span>暂无定时任务</span>
          </div>
        </div>
      </div>

      <!-- 第三行：执行历史 -->
      <div class="panel history-panel">
        <div class="panel-title">
          执行历史
          <span class="history-count">共 {{ historyTotal }} 条</span>
        </div>
        <a-table
          :columns="historyColumns"
          :data="historyList"
          :pagination="false"
          :stripe="true"
          size="mini"
          :scroll="{ y: 180 }"
          :loading="historyLoading"
        >
          <template #status="{ record }">
            <a-tag :color="getStatusColor(record.status)" size="small">
              {{ getStatusText(record.status) }}
            </a-tag>
          </template>
          <template #duration="{ record }">
            {{ record.duration ? `${record.duration.toFixed(1)}s` : '-' }}
          </template>
          <template #error="{ record }">
            <a-tooltip v-if="record.error" :content="record.error" position="tl">
              <span class="error-text">{{ truncateError(record.error) }}</span>
            </a-tooltip>
            <span v-else class="no-error">-</span>
          </template>
        </a-table>
        <div class="pagination-wrapper">
          <a-pagination
            v-model:current="historyPage"
            :total="historyTotal"
            :page-size="historyPageSize"
            size="mini"
            :show-total="false"
            :show-jumper="false"
            :show-page-size="false"
            simple
            @change="handlePageChange"
          />
        </div>
      </div>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  IconRefresh,
  IconDelete,
  IconClose,
  IconPlayArrowFill,
  IconPauseCircle,
} from '@arco-design/web-vue/es/icon'
import {
  getQueueStatus,
  clearQueue,
  clearHistory,
  getSchedulerStatus,
  getSchedulerJobs,
  getQueueHistory,
  type QueueStatus,
  type SchedulerStatus,
  type SchedulerJob,
  type TaskRecord,
} from '@/api/taskQueue'
import { getToken } from '@/utils/auth'

const loading = ref(false)
const clearingQueue = ref(false)
const clearingHistory = ref(false)
const wsConnected = ref(false)

// 历史记录分页
const historyPage = ref(1)
const historyPageSize = ref(10)
const historyTotal = ref(0)
const historyList = ref<TaskRecord[]>([])
const historyLoading = ref(false)

const queueStatus = ref<QueueStatus>({
  tag: '',
  is_running: false,
  pending_count: 0,
  pending_tasks: [],
  current_task: null,
  history_count: 0,
  recent_history: [],
})

const schedulerStatus = ref<SchedulerStatus>({
  running: false,
  job_count: 0,
  next_run_times: [],
})

const schedulerJobs = ref<SchedulerJob[]>([])

// WebSocket 连接
let ws: WebSocket | null = null
let reconnectTimer: number | null = null
let refreshTimer: number | null = null

// 获取 WebSocket URL
const getWsUrl = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const apiBase = '/api/v1/wx'
  const token = getToken()
  const tokenParam = token ? `?token=${encodeURIComponent(token)}` : ''
  return `${protocol}//${host}${apiBase}/task-queue/ws${tokenParam}`
}

// 连接 WebSocket
const connectWebSocket = () => {
  if (ws) {
    ws.close()
  }

  try {
    const wsUrl = getWsUrl()
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      wsConnected.value = true
      if (reconnectTimer) {
        clearInterval(reconnectTimer)
        reconnectTimer = null
      }
    }

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'queue_status' && message.data) {
          queueStatus.value = message.data
        }
      } catch (e) {
        console.error('解析 WebSocket 消息失败:', e)
      }
    }

    ws.onclose = () => {
      wsConnected.value = false
      if (!reconnectTimer) {
        reconnectTimer = window.setInterval(() => {
          if (!wsConnected.value) {
            connectWebSocket()
          }
        }, 5000)
      }
    }

    ws.onerror = () => {
      wsConnected.value = false
    }
  } catch (error) {
    console.error('WebSocket 连接失败:', error)
    wsConnected.value = false
  }
}

// 执行历史表格列
const historyColumns = [
  {
    title: '任务名称',
    dataIndex: 'task_name',
    width: '140px',
  },
  {
    title: '开始时间',
    dataIndex: 'start_time',
    width: '150px',
  },
  {
    title: '耗时',
    dataIndex: 'duration',
    slotName: 'duration',
    width: '70px',
  },
  {
    title: '状态',
    dataIndex: 'status',
    slotName: 'status',
    width: '70px',
  },
  {
    title: '错误信息',
    dataIndex: 'error',
    slotName: 'error',
  },
]

// 获取状态颜色
const getStatusColor = (status: string) => {
  switch (status) {
    case 'completed':
      return 'green'
    case 'running':
      return 'blue'
    case 'failed':
      return 'red'
    default:
      return 'gray'
  }
}

// 获取状态文本
const getStatusText = (status: string) => {
  switch (status) {
    case 'completed':
      return '成功'
    case 'running':
      return '执行中'
    case 'failed':
      return '失败'
    default:
      return status
  }
}

// 截断错误信息
const truncateError = (error: string) => {
  if (!error) return '-'
  if (error.length > 40) {
    return error.substring(0, 40) + '...'
  }
  return error
}

// 加载所有数据
const refreshAll = async () => {
  loading.value = true
  try {
    const [queueData, schedulerData, jobsData] = await Promise.all([
      getQueueStatus(),
      getSchedulerStatus(),
      getSchedulerJobs(),
    ])
    queueStatus.value = queueData
    schedulerStatus.value = schedulerData
    schedulerJobs.value = jobsData.jobs || []
    // 更新历史总数
    historyTotal.value = queueData.history_count || 0
    // 加载历史记录
    await loadHistory()
  } catch (error: any) {
    console.error('Refresh error:', error)
    Message.error(error.message || '加载数据失败')
  } finally {
    loading.value = false
  }
}

// 加载历史记录
const loadHistory = async () => {
  historyLoading.value = true
  try {
    const result = await getQueueHistory(historyPage.value, historyPageSize.value)
    historyList.value = result.history
    historyTotal.value = result.total
  } catch (error: any) {
    console.error('Load history error:', error)
  } finally {
    historyLoading.value = false
  }
}

// 分页变化
const handlePageChange = (page: number) => {
  historyPage.value = page
  loadHistory()
}

// 清空队列
const handleClearQueue = async () => {
  clearingQueue.value = true
  try {
    await clearQueue()
    Message.success('队列已清空')
    await refreshAll()
  } catch (error: any) {
    Message.error(error.message || '清空队列失败')
  } finally {
    clearingQueue.value = false
  }
}

// 清空历史
const handleClearHistory = async () => {
  clearingHistory.value = true
  try {
    await clearHistory()
    Message.success('历史记录已清空')
    historyPage.value = 1
    await refreshAll()
  } catch (error: any) {
    Message.error(error.message || '清空历史失败')
  } finally {
    clearingHistory.value = false
  }
}

onMounted(() => {
  refreshAll()
  connectWebSocket()
  refreshTimer = window.setInterval(() => {
    if (!wsConnected.value) {
      refreshAll()
    }
  }, 10000)
})

onUnmounted(() => {
  if (ws) {
    ws.close()
    ws = null
  }
  if (reconnectTimer) {
    clearInterval(reconnectTimer)
    reconnectTimer = null
  }
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.task-queue-view {
  padding: 12px;
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 顶部状态栏 */
.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: var(--color-bg-2);
  border-radius: 6px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-left .title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-1);
}

.header-right {
  display: flex;
  gap: 8px;
}

/* 行布局 */
.row-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

/* 面板 */
.panel {
  background: var(--color-bg-2);
  border-radius: 6px;
  padding: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.panel-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-2);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 状态面板 */
.status-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.status-item {
  text-align: center;
  padding: 8px;
  background: var(--color-fill-1);
  border-radius: 4px;
}

.status-item .label {
  display: block;
  font-size: 12px;
  color: var(--color-text-3);
  margin-bottom: 4px;
}

.status-item .value {
  display: block;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-1);
}

.status-item .value.pending {
  color: #ff7d00;
}

/* 当前任务面板 */
.current-task {
  padding: 10px;
  background: var(--color-fill-1);
  border-radius: 4px;
}

.current-task .task-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 6px;
}

.current-task .task-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--color-text-3);
}

.no-task {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  color: var(--color-text-3);
  font-size: 13px;
  gap: 6px;
}

/* 任务列表 */
.task-list, .scheduler-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.task-item, .scheduler-item {
  display: flex;
  align-items: center;
}

.scheduler-item {
  width: 100%;
  justify-content: space-between;
  padding: 6px 10px;
  background: var(--color-fill-1);
  border-radius: 4px;
  font-size: 12px;
}

.scheduler-item .job-id {
  color: var(--color-text-1);
  font-weight: 500;
}

.scheduler-item .job-time {
  color: var(--color-text-3);
}

.more-tasks {
  width: 100%;
  text-align: center;
  font-size: 12px;
  color: var(--color-text-3);
  padding: 4px;
}

/* 历史面板 */
.history-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.history-panel .panel-title {
  flex-shrink: 0;
}

.history-count {
  font-size: 12px;
  font-weight: normal;
  color: var(--color-text-3);
  margin-left: 8px;
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  padding: 8px 0;
  flex-shrink: 0;
}

.error-text {
  color: #f53f3f;
  font-size: 12px;
  cursor: pointer;
}

.no-error {
  color: var(--color-text-3);
}

/* 表格样式 */
:deep(.arco-table-wrapper) {
  flex: 1;
  min-height: 0;
}

:deep(.arco-table) {
  font-size: 12px;
}

:deep(.arco-table-th) {
  background: var(--color-fill-1);
}

:deep(.arco-table-td) {
  padding: 6px 8px;
}

/* 响应式 */
@media (max-width: 768px) {
  .row-layout {
    grid-template-columns: 1fr;
  }
  
  .header-bar {
    flex-direction: column;
    gap: 10px;
  }
  
  .header-right {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
