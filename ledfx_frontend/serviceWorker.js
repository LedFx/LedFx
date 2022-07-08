/* eslint-disable no-restricted-globals */
self.addEventListener('install', (event) => {
  event.waitUntil(Promise.resolve());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((self).clients.claim());
});

self.addEventListener('fetch', (event) => {
  event.waitUntil(Promise.resolve());
});
