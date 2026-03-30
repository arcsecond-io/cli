module.exports = {
  title: 'Arcsecond CLI',
  description: 'The command-line / Python module of Arcsecond.',
  base: '/cli/',
  themeConfig: {
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Arcsecond Docs', link: 'https://docs.arcsecond.io' }
    ],
    sidebar: [
      {
        text: 'Guide',
        items: [
          { text: 'Install', link: '/install' },
          { text: 'API Basics', link: '/api-basics' },
          { text: 'Resources', link: '/resources' }
        ]
      }
    ]
  }
}
