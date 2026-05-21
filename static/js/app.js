// app.js - Основной файл для логики фронтенда

// Функция для получения токена из cookie (для упрощенной схемы)
function getCookie(name) {
    let value = "; " + document.cookie;
    let parts = value.split("; " + name + "=");
    if (parts.length === 2) return parts.pop().split(";").shift();
}

// Функция для обработки ошибок API
function handleApiError(response) {
    if (!response.ok) {
        return response.text().then(text => {
            console.error(`API Error: ${response.status} - ${text}`);
            alert(`Ошибка: ${response.status} - ${text}`);
            throw new Error(`API Error: ${response.status} - ${text}`);
        });
    }
    return response;
}

// Функция для обновления данных в реальном времени (polling)
function startPolling(endpoint, updateFunction, intervalMs = 3000) {
    console.log(`[POLLING] Started for ${endpoint} every ${intervalMs}ms`);
    setInterval(() => {
        console.log(`[POLLING] Fetching ${endpoint}...`);
        fetch(endpoint)
            .then(handleApiError)
            .then(response => response.json())
            .then(data => {
                console.log(`[POLLING] Received data from ${endpoint}:`, data);
                updateFunction(data);
            })
            .catch(err => console.error('[POLLING] Error fetching ', err));
    }, intervalMs);
}

// Пример использования polling для обновления заявок клиента (на странице rentals)
// function updateClientRentalsView(data) {
//     // Обновить DOM с новыми данными аренд
//     console.log("Updating client rentals view...", data);
//     // ... логика обновления ...
// }
// startPolling('/api/client/rentals', updateClientRentalsView, 3000);

// Пример использования polling для обновления заявок админа (на странице dashboard/rentals)
// function updateAdminRequestsView(data) {
//     // Обновить DOM с новыми заявками
//     console.log("Updating admin requests view...", data);
//     // ... логика обновления ...
// }
// startPolling('/api/admin/rentals', updateAdminRequestsView, 3000);

console.log("[APP.JS] Loaded successfully.");