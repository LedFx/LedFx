import tv4 from 'tv4';

export function selectOrSet(projection, obj, valueToSet, type) {
    var numRe = /^\d+$/;

    if (!obj) {
        obj = this;
    }
    // Support [] array syntax
    var parts =
        typeof projection === 'string' ? Object.parse(projection) : projection;

    if (typeof valueToSet !== 'undefined' && parts.length === 1) {
        // special case, just setting one variable
        obj[parts[0]] = valueToSet;
        return obj;
    }

    if (typeof valueToSet !== 'undefined' && typeof obj[parts[0]] === 'undefined') {
        // We need to look ahead to check if array is appropriate
        obj[parts[0]] = parts.length > 2 && numRe.test(parts[1]) ? [] : {};
    }

    if (
        typeof type !== 'undefined' &&
        ['number', 'integer'].indexOf(type) > -1 &&
        typeof valueToSet === 'undefined'
    ) {
        // number or integer can undefined
        obj[parts[0]] = valueToSet;
        return obj;
    }

    var value = obj[parts[0]];
    for (var i = 1; i < parts.length; i += 1) {
        // Special case: We allow JSON Form syntax for arrays using empty brackets
        // These will of course not work here so we exit if they are found.
        if (parts[i] === '') {
            return undefined;
        }
        if (typeof valueToSet !== 'undefined') {
            if (i === parts.length - 1) {
                // last step. Let's set the value
                value[parts[i]] = valueToSet;
                return valueToSet;
            }
            // Make sure to create new objects on the way if they are not there.
            // We need to look ahead to check if array is appropriate
            var tmp = value[parts[i]];
            if (typeof tmp === 'undefined' || tmp === null) {
                tmp = numRe.test(parts[i + 1]) ? [] : {};
                value[parts[i]] = tmp;
            }
            value = tmp;
        } else if (value) {
            // Just get nex value.
            value = value[parts[i]];
        }
    }
    return value;
}

export function extractValue(e, prop) {
    let value = undefined;
    switch (prop.type) {
        case 'integer':
        case 'number':
            if (e.target.value.indexOf('.') === -1) {
                value = parseInt(e.target.value);
            } else {
                value = parseFloat(e.target.value);
            }

            if (isNaN(value) || value === null) {
                value = undefined;
            }
            break;
        case 'boolean':
            value = e.target.checked;
            break;
        default:
            value = e.target.value;

            if (value === '') {
                value = undefined;
            }
    }

    return value;
}

export function validateValue(v, prop) {
    let schema = { type: 'object', properties: {} };
    schema.properties[prop.title] = prop;
    schema.required = prop.required ? [prop.title] : [];

    let value = {};
    if (v !== undefined) {
        value[prop.title] = v;
    }

    let result = tv4.validateResult(value, schema);
    return result;
}

export function validateData(formData, schema) {
    // let schema = { type: "object", properties: formData };
    let result = tv4.validateResult(formData, schema);

    return result;
}
