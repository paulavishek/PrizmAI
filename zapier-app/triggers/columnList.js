/**
 * Internal trigger: Column List
 *
 * Fetches columns for a given board.
 * Used as a dynamic dropdown source for column_id fields.
 */
const { BASE_URL } = require('../authentication');

const SAMPLE = {
  id: 3,
  name: 'To Do',
  position: 0,
};

const perform = async (z, bundle) => {
  const boardId = bundle.inputData.board_id;
  if (!boardId) return [SAMPLE];

  const response = await z.request({
    url: `${BASE_URL}/api/v1/zapier/boards/${boardId}/columns/`,
  });
  return response.json;
};

module.exports = {
  key: 'column_list',
  noun: 'Column',
  display: {
    label: 'Column List (internal)',
    description: 'Internal trigger used to populate column dropdowns.',
    hidden: true,
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
      },
    ],
    perform,
    sample: SAMPLE,
    outputFields: [
      { key: 'id', label: 'Column ID', type: 'integer' },
      { key: 'name', label: 'Column Name' },
    ],
  },
};
