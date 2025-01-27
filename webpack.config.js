const TerserPlugin = require('terser-webpack-plugin');
const path = require('path');

module.exports = {
  mode: "development",
  entry: './src/lovelace.ts',
  module: {
    rules: [
      {
        test: /\.ts?$/,
        use: 'ts-loader',
        exclude: /node_modules/,
      },
    ],
  },
  resolve: {
    extensions: ['.tsx', '.ts', '.js'],
  },
  output: {
    path: path.resolve(__dirname, 'custom_components/postnl/'),
    filename: 'lovelace.js',
  },
  optimization: {
    minimizer: [new TerserPlugin({
      extractComments: false,
    })],
  },
};