import { combineReducers } from 'redux'
import { devicesById } from './devices'
import { schemas } from './schemas'

const rootReducer = combineReducers({
    devicesById,
    schemas,
})

export default rootReducer