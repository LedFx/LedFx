import { combineReducers } from 'redux'
import { devicesById } from './devices'
import { presets } from './presets'
import { schemas } from './schemas'
import { scenes } from './scenes'
import { settings } from './settings'

const rootReducer = combineReducers({
    devicesById,
    presets,
    schemas,
    scenes,
    settings
})

export default rootReducer