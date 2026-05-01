/**
 * Trigger: Task Completed
 *
 * Polls GET /api/v1/zapier/tasks/completed/ for tasks with progress == 100.
 */
const { BASE_URL } = require('../authentication');

const SAMPLE = {
  id: 42,
  title: 'Write unit tests',
  description: '',
  priority: 'medium',
  progress: 100,
  column_id: 5,
  column_name: 'Done',
  board_id: 1,
  board_name: 'Software Development',
  assigned_to_id: 7,
  assigned_to_username: 'avishek',
  due_date: '2026-05-10T00:00:00Z',
  start_date: null,
  created_at: '2026-04-20T08:00:00Z',
  updated_at: '2026-05-02T14:32:00Z',
};

const perform = async (z, bundle) => {
  const params = {};
  const boardId = bundle.inputData.board_id;
  if (boardId) params.board_id = boardId;

  const response = await z.request({
    url: `${BASE_URL}/api/v1/zapier/tasks/completed/`,
    params,
  });

  return response.json;
};

module.exports = {
  key: 'task_completed',
  noun: 'Task',
  display: {
    label: 'Task Completed',
    description: 'Triggers when a task reaches 100% progress in PrizmAI.',
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
      { key: 'column_name', label: 'Column / Status' },
      { key: 'board_name', label: 'Board' },
      { key: 'assigned_to_username', label: 'Completed By' },
      { key: 'updated_at', label: 'Completed At', type: 'datetime' },
    ],
  },
};
