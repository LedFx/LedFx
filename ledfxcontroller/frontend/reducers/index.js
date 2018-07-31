import { combineReducers } from 'redux'
import { effects } from './effects'
import { devicesById } from './devices'

const rootReducer = combineReducers({
    devicesById,
    effects
})

export default rootReducer