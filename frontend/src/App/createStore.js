import thunk from 'redux-thunk';
import { applyMiddleware, combineReducers, createStore } from 'redux';
import { composeWithDevTools } from 'redux-devtools-extension';
import { connectRouter, routerMiddleware } from 'connected-react-router';
import { createBrowserHistory } from 'history';

import reducers from '../modules';
import { save, load } from "redux-localstorage-simple"

export const history = createBrowserHistory();

const createStoreWithMiddleware
    = applyMiddleware(
        save({ states: ["virtuals"], debounce: 500 })
    )(createStore)


export default () => {
    const store = createStoreWithMiddleware(
        combineReducers({
            ...reducers,
            router: connectRouter(history),
        }),
        load({ states: ["virtuals"] }),
        composeWithDevTools(applyMiddleware(routerMiddleware(history), thunk))

    );

    return store;
};
