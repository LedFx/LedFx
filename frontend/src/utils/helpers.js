export const includeKeyInObject = (key, object) => ({ id: key, ...object });

export const mapIncludeKey = scenes => {
    const keys = Object.keys(scenes);
    return keys.map(k => includeKeyInObject(k, scenes[k]));
};

export const convertDictionaryToList = (presets = {}) =>
    Object.keys(presets).map(key => {
        const currentScene = presets[key];
        return {
            ...currentScene,
            id: key,
        };
    });

export const camelToSnake = str =>
    str[0].toLowerCase() +
    str.slice(1, str.length).replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
