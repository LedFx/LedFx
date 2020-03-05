import { combineReducers } from 'redux'
import { devicesById } from './devices'
import { schemas } from './schemas'
import { scenes } from './scenes'
import { settings } from './settings'

const rootReducer = combineReducers({
    devicesById,
    schemas,
    scenes,
    settings
})

export default rootReducer