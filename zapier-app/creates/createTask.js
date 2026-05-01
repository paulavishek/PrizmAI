/**
 * Action: Create Task
 *
 * Posts to POST /api/v1/zapier/tasks/create/
 */
const { BASE_URL } = require('../authentication');

const SAMPLE = {
  id: 200,
  title: 'New task from Zapier',
  description: '',
  priority: 'medium',
  progress: 0,
  column_id: 3,
  column_name: 'To Do',
  board_id: 1,
  board_name: 'Software Development',
  assigned_to_id: null,
  assigned_to_username: null,
  due_date: null,
  start_date: null,
  created_at: '2026-05-02T12:00:00Z',
  updated_at: '2026-05-02T12:00:00Z',
};

const perform = async (z, bundle) => {
  const response = await z.request({
    url: `${BASE_URL}/api/v1/zapier/tasks/create/`,
    method: 'POST',
    body: {
      title: bundle.inputData.title,
      description: bundle.inputData.description,
      board_id: bundle.inputData.board_id,
      column_id: bundle.inputData.column_id,
      priority: bundle.inputData.priority || 'medium',
      due_date: bundle.inputData.due_date,
      assigned_to: bundle.inputData.assigned_to,
    },
  });

  return response.json;
};

module.exports = {
  key: 'create_task',
  noun: 'Task',
  display: {
    label: 'Create Task',
    description: 'Creates a new task in a PrizmAI board.',
  },
  operation: {
    inputFields: [
      {
        key: 'title',
        label: 'Title',
        type: 'string',
        required: true,
        helpText: 'The title of the new task.',
      },
      {
        key: 'board_id',
        label: 'Board',
        type: 'integer',
        required: true,
        dynamic: 'board_list.id.name',
        helpText: 'The board to create the task in.',
      },
      {
        key: 'column_id',
        label: 'Column / Status',
        type: 'integer',
        required: false,
        dynamic: 'column_list.id.name',
        helpText: 'The column to place the task in. Defaults to the first column.',
      },
      {
        key: 'description',
        label: 'Description',
        type: 'text',
        required: false,
      },
      {
        key: 'priority',
        label: 'Priority',
        type: 'string',
        required: false,
        choices: ['low', 'medium', 'high', 'urgent'],
        default: 'medium',
      },
      {
        key: 'due_date',
        label: 'Due Date',
        type: 'datetime',
        required: false,
      },
    ],
    perform,
    sample: SAMPLE,
  },
};
