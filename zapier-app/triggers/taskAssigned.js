/**
 * Trigger: Task Assigned (to the authenticated user)
 *
 * Polls GET /api/v1/zapier/tasks/assigned/
 * Returns tasks assigned to the user who owns the API token.
 */
const { BASE_URL } = require('../authentication');

const SAMPLE = {
  id: 77,
  title: 'Review PR #88',
  description: 'Check the new API endpoint implementation',
  priority: 'high',
  progress: 20,
  column_id: 4,
  column_name: 'In Progress',
  board_id: 1,
  board_name: 'Software Development',
  assigned_to_id: 7,
  assigned_to_username: 'avishek',
  due_date: '2026-05-05T17:00:00Z',
  start_date: null,
  created_at: '2026-04-29T10:00:00Z',
  updated_at: '2026-05-02T09:15:00Z',
};

const perform = async (z, bundle) => {
  const params = {};
  const boardId = bundle.inputData.board_id;
  if (boardId) params.board_id = boardId;

  const response = await z.request({
    url: `${BASE_URL}/api/v1/zapier/tasks/assigned/`,
    params,
  });

  return response.json;
};

module.exports = {
  key: 'task_assigned',
  noun: 'Task',
  display: {
    label: 'Task Assigned to Me',
    description: 'Triggers when a task is assigned to the authenticated PrizmAI user.',
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
      { key: 'priority', label: 'Priority' },
      { key: 'due_date', label: 'Due Date', type: 'datetime' },
      { key: 'board_name', label: 'Board' },
      { key: 'column_name', label: 'Column / Status' },
      { key: 'updated_at', label: 'Assigned At', type: 'datetime' },
    ],
  },
};
