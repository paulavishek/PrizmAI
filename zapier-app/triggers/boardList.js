/**
 * Internal trigger: Board List
 *
 * Used as a dynamic dropdown source for board_id fields in other
 * triggers and actions.  Not surfaced directly to end users.
 */
const { BASE_URL } = require('../authentication');

const SAMPLE = {
  id: 1,
  name: 'Software Development',
  task_prefix: 'SD',
  column_count: 5,
};

const perform = async (z, bundle) => {
  const response = await z.request({
    url: `${BASE_URL}/api/v1/zapier/boards/`,
  });
  return response.json;
};

module.exports = {
  key: 'board_list',
  noun: 'Board',
  display: {
    label: 'Board List (internal)',
    description: 'Internal trigger used to populate board dropdowns.',
    hidden: true,
  },
  operation: {
    type: 'polling',
    perform,
    sample: SAMPLE,
    outputFields: [
      { key: 'id', label: 'Board ID', type: 'integer' },
      { key: 'name', label: 'Board Name' },
      { key: 'task_prefix', label: 'Task Prefix' },
    ],
  },
};
