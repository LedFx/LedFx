import { createAction, handleActions } from 'redux-actions';

// Actions
const ACTION_ROOT = 'ui';

export const snackbarSuccess = createAction(`${ACTION_ROOT}/SNACKBAR_SUCCESS`);
export const snackbarClear = createAction(`${ACTION_ROOT}/SNACKBAR_CLEAR`);

// Reducer
const INITIAL_STATE = {
    snackbar: {
        successSnackbarOpen: false,
        successSnackbarMessage: 'NO MESSAGE',
    },
};

export default handleActions(
    {
        [snackbarSuccess]: (state, { payload }) => ({
            // console.log('MESSAGE: success', payload) ||
            ...state,
            snackbar: {
                ...state.snackbar,
                successSnackbarOpen: true,
                successSnackbarMessage: payload.message,
            },
        }),
        [snackbarClear]: state => ({
            ...state,
            snackbar: {
                successSnackbarOpen: false,
                errorSnackbarOpen: false,
                infoSnackbarOpen: false,
            },
        }),
    },
    INITIAL_STATE
);

export const showSuccessSnackbar = message => {
    // console.log(message);
    return async dispatch => {
        dispatch(snackbarSuccess({ message }));
    };
};

export const clearSnackbar = () => {
    // console.log('WTF');
    return dispatch => {
        dispatch(snackbarClear());
    };
};
