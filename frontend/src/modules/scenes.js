import { createAction, handleActions } from 'redux-actions';
import * as scenesProxies from 'proxies/scenes';

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
        [scenesFetched]: (state, { payload: { scenes = {}, list = [], error = '' } }) => {
            return {
                ...state,
                dictionary: !error ? scenes : {},
                list: !error ? list : [],
                isLoading: false,
            };
        },
        [sceneAdding]: state => ({
            ...state,
            isProcessing: true,
        }),

        [sceneAdded]: (state, { payload: { id, config, error = '' } }) => {
            const scenes = {
                ...state.dictionary,
                [id]: config,
            };
            return {
                ...state,
                dictionary: !error ? scenes : {},
                list: !error ? convertScenesDictionaryToList(scenes) : [],
                isProcessing: false,
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
            console.log('Error fetching scenes', error.message);
            dispatch(scenesFetched({ error: error.message }));
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
        } catch (e) {
            console.log(' error updating sceen', e);
        }
    };
}

export function deleteScene(id) {
    return async dispatch => {
        const response = await scenesProxies.deleteScenes(id);
        dispatch(getScenes());
    };
}

export function activateScene(id) {
    return async dispatch => {
        const response = await scenesProxies.activateScenes(id);
    };
}

export function renameScene(id, name) {
    return async dispatch => {
        const response = await scenesProxies.renameScene({ id, name });
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
