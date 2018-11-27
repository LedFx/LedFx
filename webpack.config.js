const path = require("path");
const webpack = require("webpack");
const UglifyJsPlugin = require('uglifyjs-webpack-plugin');
const ExtractTextPlugin = require("extract-text-webpack-plugin");
const CopyWebpackPlugin = require("copy-webpack-plugin");

const config = {
  entry: __dirname + "/ledfx/frontend/index.jsx",
  module: {
    rules: [
      {
        test: /\.jsx?/,
        exclude: /node_modules/,
        use: [
          {
            loader: "babel-loader",
            options: {
              presets: ["stage-1", "react"]
            }
          }
        ]
      },
      {
        test: /\.css$/,
        use: ExtractTextPlugin.extract({
          fallback: "style-loader",
          use: [
            {
              loader: "css-loader",
              options: { importLoaders: 1 }
            },
            {
              loader: "postcss-loader",
              options: {
                ident: "postcss",
                plugins: () => [require("autoprefixer")()]
              }
            }
          ]
        })
      },
      {
        test: /\.(png|jpg|gif)$/,
        use: [
          {
            loader: "file-loader",
            options: {}
          }
        ]
      }
    ]
  },
  output: {
    path: __dirname + "/ledfx_frontend",
    publicPath: "/static/",
    filename: "bundle.js"
  },
  resolve: {
    extensions: [".js", ".jsx", ".css"],
    modules: [path.resolve("./ledfx"), path.resolve("./node_modules")]
  },
  plugins: [
    new webpack.DefinePlugin({
      'process.env': {
        NODE_ENV: '"production"'
      }
    }),
    new CopyWebpackPlugin([
      {from: 'ledfx/frontend/dist', to: __dirname + "/ledfx_frontend"}
    ]),
    new UglifyJsPlugin({
      uglifyOptions: {        
        ecma: 8      
      }
    }),
    new ExtractTextPlugin("style.css")
  ]
};

module.exports = config;
