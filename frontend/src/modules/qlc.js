import { createAction, handleActions } from 'redux-actions';
import * as integrationsProxies from 'proxies/integrations';

// Actions
const ACTION_ROOT = 'qlc';
export const setqlclistener = createAction(`${ACTION_ROOT}/QLCLISTENER_SET`);
export const addqlclistener = createAction(`${ACTION_ROOT}/QLCLISTENER_ADD`);

// // Reducer
const INITIAL_STATE = {
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
    //console.log("getAsyncqlclisteners: ", data)
    return async dispatch => {
        try {
            //data = ({ info: 'status' });
            const response = await integrationsProxies.getQLCInfo(data);
            if (response.statusText === 'OK') {
                //console.log("GetQLCInfo - Response: ", response.data)
                dispatch(setqlclistener(response.data));
            }
        } catch (error) {
            console.log(error);
        }
    };
}

export function createQlcListener(id,formdata) {
    console.log("id",id);
    console.log("name",formdata);
    return async dispatch => {
        try {
            const { data, statusText } = await integrationsProxies.createQLCListener(id,formdata);
            if (statusText === 'OK') {
                console.log(data);
            }
        } catch (error) {
            console.log(error);
        }
    };
}

//Need to do: create addqlclistener function
