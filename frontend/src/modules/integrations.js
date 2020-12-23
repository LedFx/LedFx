import { createAction, handleActions } from 'redux-actions';
import * as integrationsProxies from 'proxies/integrations';

const ACTION_ROOT = 'integrations';

export const addIntegration = createAction(`${ACTION_ROOT}/INTEGRATION_ADD`);
export const setIntegration = createAction(`${ACTION_ROOT}/INTEGRATION_SET`);
// export const deleteIntegration = createAction(`${ACTION_ROOT}/INTEGRATION_DELETE`);

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
    },
    INITIAL_STATE
);

export function getAsyncIntegrations() {
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

export function deleteAsyncIntegration(data) {
    console.log('damn', data);
    integrationsProxies.deleteIntegration({ data });
    return async dispatch => {
        try {
            console.log('damn', data);
            const response = await integrationsProxies.deleteIntegration(data);
            if (response.statusText === 'OK') {
                console.log('OMG', response.data);
                dispatch(setIntegration(response.data.integrations));
            }
        } catch (error) {
            console.log(error);
        }
    };
}
