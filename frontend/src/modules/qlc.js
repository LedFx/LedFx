import { createAction, handleActions } from 'redux-actions';
import * as integrationsProxies from 'proxies/integrations';

// Actions
const ACTION_ROOT = 'qlc';
export const setqlclistener = createAction(`${ACTION_ROOT}/QLCLISTENER_SET`);
export const addqlclistener = createAction(`${ACTION_ROOT}/QLCLISTENER_ADD`);

// // Reducer
const INITIAL_STATE = {
    list: []
};

export default handleActions(
    {
        [setqlclistener]: (state, { payload }) => {
            return {
                ...state,
                payload,
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
                console.log("GetQLCInfo - Response: ", response.data)
                dispatch(setqlclistener(response.data));
            }
        } catch (error) {
            console.log(error);
        }
    };
}
