# $NetBSD$

DISTNAME=	prism32-6.9.0
CATEGORIES=	misc
MASTER_SITES=	${MASTER_SITE_GITHUB:=MegaDyneSystems/}
GITHUB_PROJECT=	prism32
GITHUB_TAG=	v6.9.0

MAINTAINER=	dev@megadynesystems.com
HOMEPAGE=	https://github.com/MegaDyneSystems/prism32
COMMENT=	Self-extending polymorphic AI super-agent
LICENSE=	apache-2.0

NO_BUILD=	yes
USE_LANGUAGES=	# none
REPLACE_PYTHON+=	prism32.py

PYTHON_VERSIONS_INCOMPATIBLE=	27

INSTALLATION_DIRS+=	bin

do-install:
	${INSTALL_SCRIPT} ${WRKSRC}/prism32.py ${DESTDIR}${PREFIX}/bin/prism32

.include "../../lang/python/application.mk"
.include "../../mk/bsd.pkg.mk"
