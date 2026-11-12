<?php

// Append to web/sites/default/settings.php (from the drupal-l12 run).

/**
 * Tribune Desk integration (web/modules/custom/tribunedesk).
 *
 * Secrets come from the environment only; never put their values here or in
 * exported configuration. Names are listed in .env.example.
 */
$settings['tribunedesk'] = [
  // Signing secret of the delivery webhook (whsec_...).
  'secret' => getenv('TD_WEBHOOK_SECRET') ?: '',
  // API token with articles:write (link back), tdcms_...
  'token' => getenv('TD_CMS_TOKEN') ?: '',
  // Tribune Desk API base; tests point it at the local mock.
  'api_base' => getenv('TD_API_BASE') ?: 'https://api.tribunedesk.com',
  // Public base URL of this site, for edit and published links built by
  // drush and cron; override locally, e.g. http://127.0.0.1:8888.
  'site_url' => getenv('TD_SITE_URL') ?: 'https://news.example.com',
];

