import { createAction, handleActions } from 'redux-actions';
import * as integrationsProxies from 'proxies/integrations';

// Actions
const ACTION_ROOT = 'qlc';
export const setqlclistener = createAction(`${ACTION_ROOT}/QLCLISTENER_SET`);
export const addqlclistener = createAction(`${ACTION_ROOT}/QLCLISTENER_ADD`);

// // Reducer
const INITIAL_STATE = {
    event_types: []
};

export default handleActions(
    {
        [addqlclistener]: (state, { payload }) => {
            return {
                ...state,
                list: payload,
            };
        },
    },
    INITIAL_STATE
);

export function getAsyncqlclisteners(data) {
    console.log("getAsyncqlclisteners: ", data)
    return async dispatch => {
        try {
            const response = await integrationsProxies.getQLCInfo(data);
            if (response.statusText === 'OK') {
                console.log("GetQLCInfo - Response: ", response)
                dispatch(addqlclistener(response.data.integrations));
            }
        } catch (error) {
            console.log(error);
        }
    };
}
