import axios from 'axios';

const baseURL = 'http://localhost:8888/api';

export const api = axios.create({
    baseURL,
});
