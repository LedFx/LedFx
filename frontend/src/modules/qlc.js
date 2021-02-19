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
    },
    INITIAL_STATE
);

export function getAsyncqlclisteners() {
    return async dispatch => {
        try {
            const response = await integrationsProxies.getQLCInfo();
            if (response.statusText === 'OK') {
                dispatch(setqlclistener(response.data.qlclisteners));
            }
        } catch (error) {
            console.log(error);
        }
    };
}
