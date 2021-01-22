import { createAction, handleActions } from 'redux-actions';
import * as scenesProxies from 'proxies/scenes';
import * as deviceProxies from './devices';
import * as uiProxies from './ui';

// Actions
const ACTION_ROOT = 'sceneManagement';
export const scenesFetching = createAction(`${ACTION_ROOT}/SCENES_FETCHING`);
export const scenesFetched = createAction(`${ACTION_ROOT}/SCENES_FETCHED`);
export const sceneAdding = createAction(`${ACTION_ROOT}/SCENE_ADDING`);
export const sceneAdded = createAction(`${ACTION_ROOT}/SCENE_ADDED`);

// Reducer
const INITIAL_STATE = {
    isLoading: false,
    isProcessing: false,
    dictionary: {},
    list: [],
};

export default handleActions(
    {
        [scenesFetching]: state => ({
            ...state,
            isLoading: true,
        }),
        [scenesFetched]: (state, { payload, payload: { scenes = {}, list = [] }, error }) => {
            return {
                ...state,
                dictionary: error ? {} : scenes,
                list: error ? [] : list,
                isLoading: false,
                error: error ? payload.message : '',
            };
        },
        [sceneAdding]: state => ({
            ...state,
            isProcessing: true,
        }),

        [sceneAdded]: (state, { payload, payload: { id, config, error = '' } }) => {
            const scenes = {
                ...state.dictionary,
                [id]: config,
            };
            return {
                ...state,
                dictionary: error ? {} : scenes,
                list: error ? [] : convertScenesDictionaryToList(scenes),
                isProcessing: false,
                error: error ? payload.message : '',
            };
        },
    },
    INITIAL_STATE
);

export function getScenes() {
    return async dispatch => {
        dispatch(scenesFetching());
        try {
            const response = await scenesProxies.getScenes();

            if (response.statusText === 'OK') {
                const { scenes } = response.data;
                const list = convertScenesDictionaryToList(scenes);
                dispatch(scenesFetched({ scenes, list }));
            }
        } catch (error) {
            dispatch(scenesFetched(error));
        }
    };
}

export function addScene(name) {
    return async dispatch => {
        dispatch(sceneAdding());
        try {
            const { data, statusText } = await scenesProxies.addScenes(name);
            if (statusText === 'OK') {
                dispatch(sceneAdded(data.scene));
            }
        } catch (error) {
            dispatch(sceneAdded(error));
        }
    };
}

export function deleteScene(id) {
    return async dispatch => {
        await scenesProxies.deleteScenes(id);
        dispatch(getScenes());
    };
}

export function activateScene(id) {
    return async (dispatch, getState) => {
        const sceneDevices = getState().scenes.list.find(s => s.id === id).devices;
        const res = await scenesProxies.activateScenes(id);
        if (res.status && res.status === 200) {
            dispatch(uiProxies.showSuccessSnackbar(JSON.stringify(res.data)));
            Object.keys(sceneDevices).map(d => {
                dispatch(
                    deviceProxies.handleActiveDeviceEffect(
                        d,
                        sceneDevices[d].hasOwnProperty('config')
                    )
                );
                return false;
            });
        } else {
            dispatch(uiProxies.showSuccessSnackbar(JSON.stringify(res)));
        }
    };
}

export function renameScene(id, name) {
    return async dispatch => {
        await scenesProxies.renameScene({ id, name });
        dispatch(getScenes());
    };
}

const convertScenesDictionaryToList = (scenes = {}) =>
    Object.keys(scenes).map(key => {
        const currentScene = scenes[key];
        return {
            ...currentScene,
            key,
            id: key,
            name: currentScene.name,
        };
    });
