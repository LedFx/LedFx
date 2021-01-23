import { createAction, handleActions } from 'redux-actions';

// Actions
const ACTION_ROOT = 'ui';

export const snackbarSuccess = createAction(`${ACTION_ROOT}/SNACKBAR_SUCCESS`);
export const snackbarClear = createAction(`${ACTION_ROOT}/SNACKBAR_CLEAR`);

// Reducer
const INITIAL_STATE = {
    snackbar: {
        dynSnackbarOpen: false,
        dynSnackbarType: 'error',
        dynSnackbarMessage: 'NO MESSAGE',
    },
};

export default handleActions(
    {
        [snackbarSuccess]: (state, { payload }) => ({
            ...state,
            snackbar: {
                ...state.snackbar,
                dynSnackbarOpen: true,
                dynSnackbarMessage: payload.message,
                dynSnackbarType: payload.type ? payload.type : 'error',
            },
        }),
        [snackbarClear]: state => ({
            ...state,
            snackbar: {
                dynSnackbarOpen: false,
                dynSnackbarType: state.snackbar.dynSnackbarType,
                dynSnackbarMessage: state.snackbar.dynSnackbarMessage,
            },
        }),
    },
    INITIAL_STATE
);

export const showdynSnackbar = payload => {
    console.log(payload);
    return async dispatch => {
        dispatch(snackbarSuccess(payload));
    };
};

export const clearSnackbar = () => {
    // console.log('WTF');
    return dispatch => {
        dispatch(snackbarClear());
    };
};
