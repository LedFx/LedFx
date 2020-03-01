export const includeKeyInObject = (key, object) => ({ id: key, ...object})

export const mapIncludeKey = (presets) => {
    const keys = Object.keys(presets)
    return keys.map((k) => (includeKeyInObject(k, presets[k])))
}