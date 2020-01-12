import { combineReducers } from 'redux'
import { devicesById } from './devices'
import { schemas } from './schemas'
import { presets } from './presets'

const rootReducer = combineReducers({
    devicesById,
    schemas,
    presets
})

export default rootReducer