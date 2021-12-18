import Cookies from 'universal-cookie/es6';
import axios from 'axios';
import qs from 'qs';

export function finishAuth() {
    console.log('finishing');
    const search = window.location.search.substring(1);
    const params = JSON.parse(
        '{"' +
            decodeURI(search).replace(/"/g, '\\"').replace(/&/g, '","').replace(/=/g, '":"') +
            '"}'
    );
    const cookies = new Cookies();
    const postData = {
        client_id: '7658827aea6f47f98c8de593f1491da5',
        grant_type: 'authorization_code',
        code: params.code,
        redirect_uri: 'http://localhost:3000/integrations/',
        code_verifier: cookies.get('verifier'),
    };
    const config = { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } };
    return axios
        .post('https://accounts.spotify.com/api/token', qs.stringify(postData), config)
        .then(res => {
            let tokens = {};
            let expDate = new Date();
            expDate.setHours(expDate.getHours() + 1);
            cookies.remove('access_token');
            cookies.remove('logout', { path: '/' });
            cookies.remove('logout', { path: '/integrations' });

            cookies.set('access_token', res.data.access_token, { expires: expDate });
            cookies.set('logout', false);
            tokens.accessToken = res.data.access_token;

            let refreshExpDate = new Date();
            refreshExpDate.setDate(refreshExpDate.getDate() + 7);
            cookies.remove('refresh_token');
            cookies.set('refresh_token', res.data.refresh_token, { expires: refreshExpDate });
            tokens.refreshToken = res.data.refresh_token;
            cookies.remove('verifier');
            window.history.replaceState({}, document.title, `/integrations`);
            return tokens;
        })
        .catch(e => console.log(e));
}

export function refreshAuth() {
    console.log('refreshing');
    const cookies = new Cookies();
    const rT = cookies.get('refresh_token');
    const postData = {
        client_id: '7658827aea6f47f98c8de593f1491da5',
        grant_type: 'refresh_token',
        refresh_token: rT,
    };
    const config = { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } };
    return axios
        .post('https://accounts.spotify.com/api/token', qs.stringify(postData), config)
        .then(res => {
            let freshTokens = {};
            let expDate = new Date();
            expDate.setHours(expDate.getHours() + 1);
            cookies.remove('access_token', { path: '/integrations' });
            cookies.set('access_token', res.data.access_token, { expires: expDate });
            freshTokens.accessToken = res.data.access_token;

            let refreshExpDate = new Date();
            refreshExpDate.setDate(refreshExpDate.getDate() + 7);
            cookies.remove('refresh_token', { path: '/integrations' });
            cookies.set('refresh_token', res.data.refresh_token, { expires: refreshExpDate });
            freshTokens.refreshToken = res.data.refreshToken;

            return freshTokens;
        })
        .catch(e => console.log(e));
}

export function logoutAuth() {
    const cookies = new Cookies();
    cookies.remove('logout', { path: '/' });
    cookies.remove('logout', { path: '/integrations' });
    cookies.remove('access_token', { path: '/' });
    cookies.remove('access_token', { path: '/integrations' });

    cookies.remove('refresh_token', { path: '/integrations' });
    cookies.remove('refresh_token', { path: '/' });

    cookies.remove('logout');

    cookies.set('logout', true);
    return true;
}

export async function addTrigger(trigger) {
    const res = await axios.post('http://localhost:8888/api/integrations/spotify/spotify', trigger);
    if (res.status == 200) {
        return 'Success';
    } else {
        return 'Error';
    }
}

export async function getTrackFeatures(id, token) {
    const res = await axios.get(`https://api.spotify.com/v1/audio-features/${id}`, {
        headers: {
            Authorization: `Bearer ${token}`,
        },
    });
    if (res.status == 200) {
        return res.data;
    } else {
        return 'Error';
    }
}

export async function getTrackAnalysis(id, token) {
    const res = await axios.get(`https://api.spotify.com/v1/audio-analysis/${id}`, {
        headers: {
            Authorization: `Bearer ${token}`,
        },
    });
    if (res.status == 200) {
        return res.data;
    } else {
        return 'Error';
    }
}
