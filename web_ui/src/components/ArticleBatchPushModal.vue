<template>
  <a-modal
    v-model:visible="visible"
    title="批量推送文章"
    :ok-loading="submitting"
    @ok="handleOk"
    @cancel="handleCancel"
  >
    <a-space direction="vertical" fill size="large">
      <a-alert type="info">
        已选择 {{ selectedArticleIds.length }} 篇文章，发送时会按公众号分组，并复用已启用的 WebHook / Email 消息任务。
      </a-alert>

      <a-form :model="form" layout="vertical">
        <a-form-item label="目标任务" field="taskId" required>
          <a-select
            v-model="form.taskId"
            :loading="loading"
            :disabled="loading || !taskOptions.length"
            placeholder="请选择消息任务"
          >
            <a-option v-for="task in taskOptions" :key="task.id" :value="task.id">
              {{ formatTaskLabel(task) }}
            </a-option>
          </a-select>
        </a-form-item>
      </a-form>

      <a-empty v-if="!loading && !taskOptions.length" description="暂无可用的 WebHook / Email 任务" />
    </a-space>
  </a-modal>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { batchPushArticles } from '@/api/article'
import { listMessageTasks } from '@/api/messageTask'
import type { MessageTask } from '@/types/messageTask'

const emit = defineEmits(['success'])

const visible = ref(false)
const loading = ref(false)
const submitting = ref(false)
const fetchSequence = ref(0)
const selectedArticleIds = ref<string[]>([])
const taskOptions = ref<MessageTask[]>([])
const form = ref({
  taskId: ''
})

const DELIVERY_MESSAGE_TYPES = [1, 2]

const getMessageTypeLabel = (messageType: number) => {
  if (messageType === 1) {
    return 'WebHook'
  }
  if (messageType === 2) {
    return 'Email'
  }
  return 'Message'
}

const formatTaskLabel = (task: MessageTask) => {
  return `${task.name} + ${getMessageTypeLabel(task.message_type)}`
}

const resetForm = () => {
  form.value.taskId = ''
}

const fetchTaskOptions = async () => {
  const currentFetchSequence = fetchSequence.value + 1
  fetchSequence.value = currentFetchSequence
  loading.value = true
  taskOptions.value = []
  form.value.taskId = ''
  try {
    const allTasks: MessageTask[] = []
    const limit = 100
    let offset = 0
    let total = 0

    do {
      const res = await listMessageTasks({
        offset,
        limit,
        status: 1
      })
      const pageTasks = res?.list || []
      total = res?.total || pageTasks.length
      allTasks.push(...pageTasks)
      offset += pageTasks.length
      if (!pageTasks.length) {
        break
      }
    } while (offset < total)

    if (currentFetchSequence !== fetchSequence.value) {
      return
    }

    taskOptions.value = allTasks.filter((task) => DELIVERY_MESSAGE_TYPES.includes(task.message_type))
    if (taskOptions.value.length > 0) {
      form.value.taskId = taskOptions.value[0].id
    }
  } catch (error) {
    if (currentFetchSequence !== fetchSequence.value) {
      return
    }
    console.error('获取消息任务列表失败:', error)
    taskOptions.value = []
  } finally {
    if (currentFetchSequence === fetchSequence.value) {
      loading.value = false
    }
  }
}

const show = async (articleIds: Array<string | number>) => {
  selectedArticleIds.value = articleIds
    .map((id) => String(id).trim())
    .filter((id) => id.length > 0)
  resetForm()
  taskOptions.value = []
  visible.value = true
  await fetchTaskOptions()
}

const hide = () => {
  visible.value = false
  resetForm()
}

const handleOk = async () => {
  if (!selectedArticleIds.value.length) {
    Message.error('请至少选择一篇文章')
    return
  }
  if (!form.value.taskId) {
    Message.error('请选择目标消息任务')
    return
  }

  submitting.value = true
  try {
    const result = await batchPushArticles({
      task_id: form.value.taskId,
      article_ids: selectedArticleIds.value
    })
    Message.success(result?.summary || '批量推送成功')
    emit('success', result)
    hide()
  } catch (error) {
    console.error('批量推送文章失败:', error)
    Message.error(String(error || '批量推送失败'))
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  hide()
}

defineExpose({
  show,
  hide
})
</script>
