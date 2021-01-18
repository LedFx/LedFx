import thunk from 'redux-thunk'
import { applyMiddleware, combineReducers, createStore } from 'redux'
import { composeWithDevTools } from 'redux-devtools-extension'
import { connectRouter, routerMiddleware } from 'connected-react-router'
import { createBrowserHistory } from 'history'
import reducers from '../modules'

export const history = createBrowserHistory()

export default () => {
    const store = createStore(
        combineReducers({
            ...reducers,
            router: connectRouter(history),
        }),
        composeWithDevTools(applyMiddleware(routerMiddleware(history), thunk))
    )
    return store
}
