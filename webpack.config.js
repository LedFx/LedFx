const path = require('path');
const webpack = require('webpack');
const ExtractTextPlugin = require('extract-text-webpack-plugin');

const config = {
  entry: __dirname + '/ledfxcontroller/frontend/index.jsx',
  module: {
    rules: [
      {
        test: /\.jsx?/,
        exclude: /node_modules/,
        use: 'babel-loader'
      },
      {
        test: /\.css$/,
        use: ExtractTextPlugin.extract({
          fallback: 'style-loader',
          use: [ 
            { 
              loader: 'css-loader', 
              options: { importLoaders: 1 } 
            }, 
            { 
              loader: 'postcss-loader', 
              options: {
                ident: 'postcss',
                plugins: () => [ require('autoprefixer')() ]
              }
            }
          ]
        })
      },
      {
        test: /\.(png|jpg|gif)$/,
        use: [
          {
            loader: 'file-loader',
            options: {}  
          }
        ]
      }
    ]
  },
  output: {
    path: __dirname + '/frontend_dist',
    publicPath: "/static/",
    filename: 'bundle.js',
  },
  resolve: {
    extensions: ['.js', '.jsx', '.css'],
    modules: [
        path.resolve('./ledfxcontroller'),
        path.resolve('./node_modules')
      ]
  },
  plugins: [
    new ExtractTextPlugin('style.css')
  ]
};

module.exports = config;