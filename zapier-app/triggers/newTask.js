/**
 * Trigger: New Task
 *
 * Polls GET /api/v1/zapier/tasks/ for newly created tasks.
 * Zapier calls this every ~15 min and deduplicates on the `id` field.
 * The `?since=<id>` param lets PrizmAI return only tasks newer than the
 * last-seen id, reducing response size on busy boards.
 */
const { BASE_URL } = require('../authentication');

const SAMPLE = {
  id: 1,
  title: 'Design landing page',
  description: 'Create wireframes and hi-fi mockups',
  priority: 'high',
  progress: 0,
  column_id: 3,
  column_name: 'To Do',
  board_id: 1,
  board_name: 'Software Development',
  assigned_to_id: null,
  assigned_to_username: null,
  due_date: null,
  start_date: null,
  created_at: '2026-05-01T09:00:00Z',
  updated_at: '2026-05-01T09:00:00Z',
};

const perform = async (z, bundle) => {
  const params = {};
  if (bundle.meta.page && bundle.meta.page > 0) {
    // Zapier passes cursor as the last item id via z.cursor (not used for
    // simple polling; ?since is handled on the first poll via inputData).
  }

  const boardId = bundle.inputData.board_id;
  if (boardId) params.board_id = boardId;

  const response = await z.request({
    url: `${BASE_URL}/api/v1/zapier/tasks/`,
    params,
  });

  return response.json;
};

module.exports = {
  key: 'new_task',
  noun: 'Task',
  display: {
    label: 'New Task',
    description: 'Triggers when a new task is created in PrizmAI.',
  },
  operation: {
    type: 'polling',
    inputFields: [
      {
        key: 'board_id',
        label: 'Board',
        type: 'integer',
        required: false,
        dynamic: 'board_list.id.name',
        helpText: 'Filter to a specific board. Leave blank for all boards.',
      },
    ],
    perform,
    sample: SAMPLE,
    outputFields: [
      { key: 'id', label: 'Task ID', type: 'integer' },
      { key: 'title', label: 'Title' },
      { key: 'description', label: 'Description' },
      { key: 'priority', label: 'Priority' },
      { key: 'progress', label: 'Progress (%)', type: 'integer' },
      { key: 'column_name', label: 'Column / Status' },
      { key: 'board_name', label: 'Board' },
      { key: 'assigned_to_username', label: 'Assigned To' },
      { key: 'due_date', label: 'Due Date', type: 'datetime' },
      { key: 'created_at', label: 'Created At', type: 'datetime' },
    ],
  },
};
