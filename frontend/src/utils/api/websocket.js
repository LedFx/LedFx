import Sockette from 'sockette';

const { NODE_ENV } = process.env;
const { hostname, port } = window.location;

const wsBaseUrl = NODE_ENV === 'development' ? 'localhost:8888' : `${hostname}:${port}`;

export const websocketUrl = `ws://${wsBaseUrl}/api/websocket`;

export const createWebSocket = options =>
    new Sockette(websocketUrl, {
        timeout: 5e3,
        maxAttempts: 10,
        ...options,
    });
