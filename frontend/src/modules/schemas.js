import { createAction, handleActions } from 'redux-actions';
import * as schemaProxies from 'proxies/schema';

// Actions
const ACTION_ROOT = 'schemas';
export const schemasFetching = createAction(`${ACTION_ROOT}/SCHEMAS_FETCHING`);
export const schemasFetched = createAction(`${ACTION_ROOT}/SCHEMAS_FETCHED`);

// Reducer
const INITIAL_STATE = {
    isLoading: false,
    deviceTypes: undefined,
    effects: undefined,
};

export default handleActions(
    {
        [schemasFetching]: state => ({
            ...state,
            isLoading: true,
        }),
        [schemasFetched]: (state, { payload, payload: { deviceTypes, effects }, error }) => ({
            ...state,
            isLoading: false,
            effects: error ? {} : effects,
            deviceTypes: error ? {} : deviceTypes,
            error: error ? payload.message : '',
        }),
    },
    INITIAL_STATE
);

export function fetchSchemas() {
    return async dispatch => {
        dispatch(schemasFetching());
        try {
            const response = await schemaProxies.getSchemas();
            if (response.statusText === 'OK') {
                const { devices: deviceTypes, effects } = response.data;
                dispatch(schemasFetched({ deviceTypes, effects }));
            }
        } catch (error) {
            dispatch(schemasFetched(error));
        }
    };
}
