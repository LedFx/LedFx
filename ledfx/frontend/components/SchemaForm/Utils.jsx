import tv4 from "tv4";

export function extractValue(e, prop) {
  let value = undefined;
  switch (prop.type) {
    case "integer":
    case "number":
      if (e.target.value.indexOf(".") == -1) {
        value = parseInt(e.target.value);
      } else {
        value = parseFloat(e.target.value);
      }

      if (isNaN(value) || value === null) {
        value = undefined;
      }
      break;
    case "boolean":
      value = e.target.checked;
      break;
    default:
      value = e.target.value;

      if (value === "") {
        value = undefined;
      }
  }

  return value;
}

export function validateValue(v, prop) {
  let schema = { type: "object", properties: { } };
  schema.properties[prop.title] = prop
  schema.required = prop.required ? [prop.title] : []

  let value = {};
  if (v !== undefined) {
    value[prop.title] = v
  }

  let result = tv4.validateResult(value, schema);
  return result;
}

export function validateData(formData, schema) {
    // let schema = { type: "object", properties: formData };
    let result = tv4.validateResult(formData, schema);
  
    return result;
  }

