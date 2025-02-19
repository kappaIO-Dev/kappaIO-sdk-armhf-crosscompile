#ifndef EPT_DEBTAGS_SOURCEDIR_H
#define EPT_DEBTAGS_SOURCEDIR_H

/** @file
 * @author Enrico Zini <enrico@enricozini.org>
 * Debtags data source directory access
 */

/*
 * Copyright (C) 2003,2004,2005,2006,2007  Enrico Zini <enrico@debian.org>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 */

#include <wibble/sys/fs.h>
#include <string>

namespace ept {
namespace debtags {

class Vocabulary;

/**
 * Access a directory containing Debtags data files
 */
class SourceDir : public wibble::sys::fs::Directory
{
protected:
	enum FileType { SKIP, TAG, VOC, TAGGZ, VOCGZ };

	// Check if a file name is a tag file, a vocabulary file or a file to skip.
	// Please notice that it works on file names, not paths.
	FileType fileType(const std::string& name);

public:
	SourceDir(const std::string& path) : Directory(path) {}

	/// Return the time of the newest file in the source directory
	time_t timestamp();

	/// Return the time of the newest vocabulary file in the source directory
	time_t vocTimestamp();

	/// Return the time of the newest tag file in the source directory
	time_t tagTimestamp();

	/// Read the tag files in the directory and output their content to out
	template<typename OUT>
	void readTags(OUT out);

	/**
	 * Read the vocabulary files in the directory and output their content to
	 * out
	 */
	void readVocabularies(Vocabulary& out);
};

}
}

// vim:set ts=4 sw=4:
#endif
