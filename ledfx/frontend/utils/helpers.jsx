export const includeKeyInObject = (key, object) => ({ id: key, ...object})

export const mapIncludeKey = (scenes) => {
    const keys = Object.keys(scenes)
    return keys.map((k) => (includeKeyInObject(k, scenes[k])))
}