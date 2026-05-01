/**
 * PrizmAI Zapier App
 * ==================
 * Connects PrizmAI (prizmai.app) to 6,000+ apps via Zapier.
 *
 * Triggers (PrizmAI → Zapier):
 *   - New Task
 *   - Task Completed
 *   - Task Assigned to Me
 *
 * Actions (Zapier → PrizmAI):
 *   - Create Task
 *   - Update Task Status
 *
 * Authentication: PrizmAI API Token
 *   Generate at: https://<your-domain>/api/v1/auth/tokens/
 *
 * ────────────────────────────────────────────────────────────────────────
 * NOTE — Marketplace Submission Checklist:
 *   This app is currently private/internal (for testing and power users).
 *   When PrizmAI is deployed on a public server, follow these steps to
 *   publish on Zapier's marketplace:
 *
 *   1.  Deploy PrizmAI to a public HTTPS domain.
 *   2.  Set PRIZMAI_BASE_URL env var to your production URL.
 *   3.  Create a Zapier developer account at https://developer.zapier.com/
 *   4.  Run: `npx zapier login` and `npx zapier register "PrizmAI"`
 *   5.  Run: `npx zapier push` to upload this definition.
 *   6.  Test all triggers and actions via the Zapier UI.
 *   7.  Submit for Zapier's review at https://platform.zapier.com/publish/
 *       — Include app description, logo (256×256 px), and category.
 *       — Zapier requires OAuth 2.0 for public apps; swap authentication.js
 *         to OAuth 2.0 at that point (PrizmAI will need an OAuth provider).
 * ────────────────────────────────────────────────────────────────────────
 */

const { version: platformVersion } = require('zapier-platform-core');
const { authentication, addAuthHeader } = require('./authentication');

// Triggers
const newTask = require('./triggers/newTask');
const taskCompleted = require('./triggers/taskCompleted');
const taskAssigned = require('./triggers/taskAssigned');
const boardList = require('./triggers/boardList');
const columnList = require('./triggers/columnList');

// Creates (Actions)
const createTask = require('./creates/createTask');
const updateTaskStatus = require('./creates/updateTaskStatus');

const App = {
  version: require('./package.json').version,
  platformVersion,

  authentication,

  beforeRequest: [addAuthHeader],

  afterResponse: [],

  resources: {},

  triggers: {
    [newTask.key]: newTask,
    [taskCompleted.key]: taskCompleted,
    [taskAssigned.key]: taskAssigned,
    [boardList.key]: boardList,
    [columnList.key]: columnList,
  },

  creates: {
    [createTask.key]: createTask,
    [updateTaskStatus.key]: updateTaskStatus,
  },

  searches: {},
};

module.exports = App;
