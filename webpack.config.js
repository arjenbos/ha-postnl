const TerserPlugin = require('terser-webpack-plugin');
const path = require('path');

module.exports = {
  entry: './src/lovelace.js',
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