import { createAction, handleActions } from 'redux-actions';
import * as integrationsProxies from 'proxies/integrations';

// Actions
const ACTION_ROOT = 'qlc';
export const setqlclistener = createAction(`${ACTION_ROOT}/qlclistener_SET`);
export const addqlclistener = createAction(`${ACTION_ROOT}/qlclistener_ADD`);
export const deleteqlclistener = createAction(`${ACTION_ROOT}/qlclistener_DELETE`);

// // Reducer
const INITIAL_STATE = {
    list: [],
};

export default handleActions(
    {
        [addqlclistener]: (state, { payload }) => {
            return {
                ...state,
                list: [
                    ...state.list,
                    {
                        payload,
                    },
                ],
            };
        },
        [setqlclistener]: (state, { payload }) => {
            return {
                ...state,
                list: payload,
            };
        },
        [deleteqlclistener]: (state, { payload }) => {
            return { ...state, list: state.list.filter(v => v.id !== payload.id) };
        },
    },
    INITIAL_STATE
);

export function getAsyncqlclisteners() {
    return async dispatch => {
        try {
            const response = await integrationsProxies.getQLCEventTypes();
            if (response.statusText === 'OK') {
                dispatch(setqlclistener(response.data.qlclisteners));
            }
        } catch (error) {
            console.log(error);
        }
    };
}

export async function deleteAsyncqlclistener(data) {
    console.log('damn', data);
    const response = await integrationsProxies.deleteqlclistener({ data });
    console.log('damn', response);
    window.location = window.location.href;
    // qlclistenersProxies.deleteqlclistener(data);
    return async dispatch => {
        try {
            console.log('damn', data);
            const response = await integrationsProxies.deleteqlclistener(data);
            if (response.statusText === 'OK') {
                console.log('OMG', response.data);
                // dispatch(deleteqlclistener(response.data.qlclisteners));
            }
        } catch (error) {
            console.log(error);
        }
    };
}

export async function toggleAsyncqlclistener(data) {
    console.log('damn', data);
    const response = await integrationsProxies.toggleqlclistener(data);
    console.log('damn', response);
    // window.location = window.location.href;
    // qlclistenersProxies.deleteqlclistener(data);
    return async dispatch => {
        try {
            console.log('damn', data);
            const response = await integrationsProxies.toggleqlclistener(data);
            if (response.statusText === 'OK') {
                console.log('OMG', response.data);
                // dispatch(deleteqlclistener(response.data.qlclisteners));
            }
        } catch (error) {
            console.log(error);
        }
    };
}
