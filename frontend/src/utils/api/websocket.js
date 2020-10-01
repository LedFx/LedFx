import Sockette from 'sockette';

const wsBaseUrl = 'ws://localhost:8888'
export const websocketUrl = `${wsBaseUrl}/api/websocket`;


export const createWebSocket = (options) => new Sockette(websocketUrl, {
    timeout: 5e3,
    maxAttempts: 10,
    ...options,
});
