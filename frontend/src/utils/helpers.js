export const includeKeyInObject = (key, object) => ({ id: key, ...object})

export const mapIncludeKey = (scenes) => {
    const keys = Object.keys(scenes)
    return keys.map((k) => (includeKeyInObject(k, scenes[k])))
}

export const convertDictionaryToList = (presets = {}) =>
    Object.keys(presets).map(key => {
        const currentScene = presets[key];
        return {
            ...currentScene,
            id: key,
        };
    });