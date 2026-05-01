/**
 * PrizmAI Zapier App — Authentication Module
 *
 * Uses PrizmAI's API Token system (same token used for the REST API).
 * Users generate tokens at: https://<your-domain>/api/v1/auth/tokens/
 *
 * NOTE (Marketplace readiness):
 *   This app is currently configured for private/internal use.
 *   Before submitting to Zapier's public marketplace:
 *     1. Register at https://developer.zapier.com/
 *     2. Create a new integration and get a Client ID
 *     3. Replace the baseUrl in .zapierapprc with your production domain
 *     4. Run `zapier push` to upload the app definition
 *     5. Complete Zapier's review checklist at https://platform.zapier.com/publish/
 */

const BASE_URL = process.env.PRIZMAI_BASE_URL || 'http://localhost:8000';

const authentication = {
  type: 'custom',
  test: {
    url: `${BASE_URL}/api/v1/auth/user/`,
    method: 'GET',
    headers: {
      Authorization: 'Token {{bundle.authData.api_token}}',
    },
  },
  fields: [
    {
      key: 'api_token',
      label: 'API Token',
      required: true,
      type: 'password',
      helpText:
        'Generate a token in PrizmAI: go to **Profile → API Tokens → Create Token**. ' +
        'Make sure it has at minimum the `tasks.read`, `tasks.write`, and `boards.read` scopes.',
    },
  ],
  connectionLabel: '{{bundle.inputData.username}}',
};

const addAuthHeader = (request, z, bundle) => {
  request.headers = request.headers || {};
  request.headers['Authorization'] = `Token ${bundle.authData.api_token}`;
  return request;
};

module.exports = { authentication, addAuthHeader, BASE_URL };
