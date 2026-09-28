const CACHE_NAME = 'moex-analyzer-v1';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
    // Просто пропускаем все запросы к серверу
    // (офлайн-режим не нужен — данные всегда свежие)
    event.respondWith(fetch(event.request));
});