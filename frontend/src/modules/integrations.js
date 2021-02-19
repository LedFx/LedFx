import { createAction, handleActions } from 'redux-actions';
import * as integrationsProxies from 'proxies/integrations';

const ACTION_ROOT = 'integrations';

export const addIntegration = createAction(`${ACTION_ROOT}/INTEGRATION_ADD`);
// export const getIntegrations = createAction(`${ACTION_ROOT}/INTEGRATIONS_GET`);
export const setIntegration = createAction(`${ACTION_ROOT}/INTEGRATION_SET`);
export const deleteIntegration = createAction(`${ACTION_ROOT}/INTEGRATION_DELETE`);

const INITIAL_STATE = {
    list: [],
};

export default handleActions(
    {
        [addIntegration]: (state, { payload }) => {
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
        [setIntegration]: (state, { payload }) => {
            return {
                ...state,
                list: payload,
            };
        },
        [deleteIntegration]: (state, { payload }) => {
            return { ...state, list: state.list.filter(v => v.id !== payload.id) };
        },
    },
    INITIAL_STATE
);

export function getAsyncIntegrations() {
    console.log("YZ02")
    return async dispatch => {
        try {
            const response = await integrationsProxies.getIntegrations();
            if (response.statusText === 'OK') {
                dispatch(setIntegration(response.data.integrations));
            }
        } catch (error) {
            console.log(error);
        }
    };
}

export async function deleteAsyncIntegration(data) {
    console.log('damn', data);
    const response = await integrationsProxies.deleteIntegration({ data });
    console.log('damn', response);
    window.location = window.location.href;
    // integrationsProxies.deleteIntegration(data);
    return async dispatch => {
        try {
            console.log('damn', data);
            const response = await integrationsProxies.deleteIntegration(data);
            if (response.statusText === 'OK') {
                console.log('OMG', response.data);
                // dispatch(deleteIntegration(response.data.integrations));
            }
        } catch (error) {
            console.log(error);
        }
    };
}

export async function toggleAsyncIntegration(data) {
    console.log('damn', data);
    const response = await integrationsProxies.toggleIntegration(data);
    console.log('damn', response);
    // window.location = window.location.href;
    // integrationsProxies.deleteIntegration(data);
    return async dispatch => {
        try {
            console.log('damn', data);
            const response = await integrationsProxies.toggleIntegration(data);
            if (response.statusText === 'OK') {
                console.log('OMG', response.data);
                // dispatch(deleteIntegration(response.data.integrations));
            }
        } catch (error) {
            console.log(error);
        }
    };
}
