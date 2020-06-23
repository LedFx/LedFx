import thunk from 'redux-thunk';
// import createSagaMiddleware from 'redux-saga';
import { applyMiddleware, combineReducers, createStore } from 'redux';
import { composeWithDevTools } from 'redux-devtools-extension';
import { connectRouter, routerMiddleware } from 'connected-react-router';
import { createBrowserHistory } from 'history';

import reducers from '../modules';
// import SagaManager from './sagas';

// const __DEV__ = process.env.NODE_ENV === 'development';

export const history = createBrowserHistory();

export default () => {
    // let sagaMonitor;

    // const sagaMiddleware = createSagaMiddleware({
    //     sagaMonitor,
    //     onError: (error: MyError) => {
    //         console.log('what the error', error);
    //         let message = error.sagaStack;
    //         if (!message && error.stack) {
    //             message =
    //                 error.stack.split('\n')[0].indexOf(error.message) !== -1
    //                     ? error.stack
    //                     : `Error: ${error.message}\n${error.stack}`;
    //         }

    //         if (__DEV__) {
    //             console.log(`redux-saga error: ${message}\n${(error && error.stack) || error}`);
    //         }
    //     },
    // });

    const store = createStore(
        combineReducers({
            ...reducers,
            router: connectRouter(history),
        }),
        composeWithDevTools(applyMiddleware(routerMiddleware(history), thunk))
    );

    // SagaManager.startSagas(sagaMiddleware);

    return store;
};
