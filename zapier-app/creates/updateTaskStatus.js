/**
 * Action: Update Task Status
 *
 * Calls PATCH /api/v1/zapier/tasks/<task_id>/status/
 * Moves the task to a different column (status).
 */
const { BASE_URL } = require('../authentication');

const SAMPLE = {
  id: 42,
  title: 'Design landing page',
  column_id: 4,
  column_name: 'In Review',
  board_id: 1,
  board_name: 'Software Development',
  progress: 80,
  updated_at: '2026-05-02T15:00:00Z',
};

const perform = async (z, bundle) => {
  const taskId = bundle.inputData.task_id;
  if (!taskId) {
    throw new z.errors.HaltedError('task_id is required.');
  }

  const body = {};
  if (bundle.inputData.column_id) {
    body.column_id = bundle.inputData.column_id;
  } else if (bundle.inputData.column_name) {
    body.column_name = bundle.inputData.column_name;
  } else {
    throw new z.errors.HaltedError('Provide either column_id or column_name.');
  }

  if (bundle.inputData.progress !== undefined && bundle.inputData.progress !== '') {
    body.progress = parseInt(bundle.inputData.progress, 10);
  }

  const response = await z.request({
    url: `${BASE_URL}/api/v1/zapier/tasks/${taskId}/status/`,
    method: 'PATCH',
    body,
  });

  return response.json;
};

module.exports = {
  key: 'update_task_status',
  noun: 'Task',
  display: {
    label: 'Update Task Status',
    description: 'Moves a PrizmAI task to a different column (status).',
  },
  operation: {
    inputFields: [
      {
        key: 'task_id',
        label: 'Task ID',
        type: 'integer',
        required: true,
        helpText: 'The numeric ID of the task to update.',
      },
      {
        key: 'column_id',
        label: 'Column (by ID)',
        type: 'integer',
        required: false,
        helpText: 'Move task to this column. Provide either Column ID or Column Name.',
      },
      {
        key: 'column_name',
        label: 'Column (by Name)',
        type: 'string',
        required: false,
        helpText: 'Move task to the column matching this name (case-insensitive). E.g. "In Review".',
      },
      {
        key: 'progress',
        label: 'Progress (%)',
        type: 'integer',
        required: false,
        helpText: 'Optionally update the task progress (0–100).',
      },
    ],
    perform,
    sample: SAMPLE,
  },
};
